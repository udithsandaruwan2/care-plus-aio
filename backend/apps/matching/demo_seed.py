"""Showcase synthetic data — every live Care Plus situation for demos.

Login (password ``CarePlus!demo`` unless noted)::

    demo.patient@careplus.local     active care, messages, records, vitals, pending hire
    demo.caregiver@careplus.local   that patient's caregiver (inbox + schedule)
    demo.admin@careplus.local       hub admin / analytics / leads
    demo.auditor@careplus.local     read-only audit role
    demo.tamil@careplus.local       Tamil / Jaffna patient
    demo.pay@careplus.local         accepted request awaiting payment
    demo.failed@careplus.local      failed card payment
    demo.onboarding@careplus.local  incomplete profile (hire gated)
    demo.alumni@careplus.local      ended care + reviews
    seed.pt.000@careplus.local      extra marketplace patient (seed-pass-change-me)
"""

from __future__ import annotations

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.catalog.checkout import create_checkout_order
from apps.catalog.models import AddOn, CarePackage
from apps.catalog.payments.service import (
    apply_payment_failure,
    confirm_mock_payment,
    create_payment_intent,
)
from apps.health_monitoring.models import HealthEvent, HealthEventType, HealthMetricKind
from apps.health_monitoring.services import ingest_metric
from apps.leads.models import Lead, LeadStatus
from apps.matching.care_relationships import end_relationship
from apps.matching.care_requests import (
    accept_care_request,
    cancel_care_request,
    create_care_request,
    reject_care_request,
)
from apps.matching.models import (
    CaregiverAvailabilitySlot,
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    MatchResult,
    PatientProfile,
    Review,
    ReviewStatus,
    Shift,
    ShiftStatus,
    create_match_run,
)
from apps.matching.patient_profile import patient_profile_completion
from apps.matching.seed_avatars import ensure_caregiver_avatar
from apps.matching.seed_data import SRI_LANKA_CITIES
from apps.medical_records.services import create_medical_record
from apps.messaging.services import get_or_create_thread_for_relationship, send_message
from apps.voice.models import Urgency, create_voice_intent
from apps.voice.session import get_or_create_active_session
from apps.vocab.models import ConditionTerm

User = get_user_model()

DEMO_PASSWORD = "CarePlus!demo"
SHOWCASE = "[showcase]"
COLOMBO = SRI_LANKA_CITIES[0]
JAFFNA = SRI_LANKA_CITIES[7]


def ensure_user(*, email: str, role: str, first_name: str, last_name: str, **extra):
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=DEMO_PASSWORD,
            role=role,
            first_name=first_name,
            last_name=last_name,
            **extra,
        )
    else:
        user.role = role
        user.first_name = first_name
        user.last_name = last_name
        for key, value in extra.items():
            setattr(user, key, value)
        user.set_password(DEMO_PASSWORD)
        user.save()
    return user


def grant_consent(user) -> None:
    for scope in ConsentScope.values:
        if ConsentLog.is_granted(user, scope):
            continue
        ConsentLog.objects.create(user=user, scope=scope, granted=True)


def complete_patient(
    user,
    *,
    display_name: str,
    city: str,
    lon: float,
    lat: float,
    preferred_language: str,
    languages: list[str],
    conditions: list[str],
    care_level: str,
    **extra,
) -> PatientProfile:
    defaults = {
        "display_name": display_name,
        "city": city,
        "location": Point(lon, lat, srid=4326),
        "preferred_language": preferred_language,
        "languages": languages,
        "conditions": conditions,
        "care_level": care_level,
        "height_cm": extra.pop("height_cm", 168),
        "weight_kg": extra.pop("weight_kg", 64.0),
        "blood_type": extra.pop("blood_type", "O+"),
        "medications": extra.pop("medications", []),
        "allergies": extra.pop("allergies", []),
        "emergency_contact_name": extra.pop("emergency_contact_name", "Family contact"),
        "emergency_contact_phone": extra.pop("emergency_contact_phone", "+94771234567"),
    }
    defaults.update(extra)
    profile, _ = PatientProfile.objects.update_or_create(user=user, defaults=defaults)
    return profile


def ensure_caregiver(
    user,
    *,
    display_name: str,
    city: str,
    lon: float,
    lat: float,
    languages: list[str],
    specialties: list[str],
    care_levels: list[str],
    **extra,
) -> CaregiverProfile:
    defaults = {
        "display_name": display_name,
        "city": city,
        "location": Point(lon, lat, srid=4326),
        "languages": languages,
        "specialties": specialties,
        "care_levels": care_levels,
        "certifications": extra.pop(
            "certifications",
            ["NVQ Level 4 Caregiving", "First Aid (Red Cross)", "CPR Certified"],
        ),
        "trust_score": extra.pop("trust_score", 0.91),
        "bio": extra.pop("bio", f"Community caregiver based near {city}."),
        "nic_id": extra.pop("nic_id", "198765432V"),
        "date_of_birth": extra.pop(
            "date_of_birth", timezone.localdate() - timedelta(days=34 * 365)
        ),
        "years_experience": extra.pop("years_experience", 8),
        "service_radius_km": extra.pop("service_radius_km", 25.0),
        "certification_docs": extra.pop(
            "certification_docs",
            [{"name": "NVQ Level 4 Caregiving", "status": "verified"}],
        ),
        "is_approved": extra.pop("is_approved", True),
        "is_active": extra.pop("is_active", True),
        "is_available": extra.pop("is_available", True),
        "embedding": [],
    }
    profile, _ = CaregiverProfile.objects.update_or_create(user=user, defaults=defaults)
    ensure_caregiver_avatar(profile)
    return profile


def seed_cg(index: int) -> CaregiverProfile:
    return CaregiverProfile.objects.select_related("user").get(
        user__email=f"seed.cg.{index:03d}@careplus.local"
    )


def _hire(
    *,
    patient,
    caregiver: CaregiverProfile,
    message: str,
    pay: bool = False,
    fail_pay: bool = False,
    package_slug: str = "intermediate-nursing",
):
    req = create_care_request(patient=patient, caregiver=caregiver, message=message)
    req, rel = accept_care_request(req, caregiver_user=caregiver.user)
    package = CarePackage.objects.get(slug=package_slug)
    addon = AddOn.objects.filter(slug="meal-support").first()
    order = create_checkout_order(
        patient=patient,
        care_request_id=req.pk,
        package_id=package.pk,
        addon_ids=[addon.pk] if addon else None,
        days=7,
    )
    intent = create_payment_intent(patient=patient, order_id=order.pk)
    if fail_pay:
        apply_payment_failure(
            payment_intent=intent,
            failure_code="card_declined",
            failure_message="[showcase] Demo card was declined.",
        )
        return req, rel, order, intent
    if pay:
        confirm_mock_payment(patient=patient, provider_intent_id=intent.provider_intent_id)
        rel.refresh_from_db()
    return req, rel, order, intent


def showcase_already_present() -> bool:
    return CareRequest.objects.filter(message__startswith=SHOWCASE).exists()


def build_showcase() -> dict[str, int]:
    """Create the situation graph. Call only when no showcase rows exist."""
    stats: dict[str, int] = {}

    admin = ensure_user(
        email="demo.admin@careplus.local",
        role=Role.ADMIN,
        first_name="Udith",
        last_name="Admin",
        is_staff=True,
        is_superuser=True,
    )
    ensure_user(
        email="demo.auditor@careplus.local",
        role=Role.AUDITOR,
        first_name="Nisha",
        last_name="Auditor",
        is_staff=True,
    )

    patient = ensure_user(
        email="demo.patient@careplus.local",
        role=Role.PATIENT,
        first_name="Sunil",
        last_name="Jayawardena",
    )
    complete_patient(
        patient,
        display_name="Sunil Jayawardena",
        city="Colombo",
        lon=COLOMBO[1],
        lat=COLOMBO[2],
        preferred_language="Sinhala",
        languages=["Sinhala", "English"],
        conditions=["diabetes", "hypertension"],
        care_level="intermediate",
        medications=["Metformin 500mg", "Amlodipine 5mg"],
        allergies=["Sulfa drugs"],
        emergency_contact_name="Malini Jayawardena",
        emergency_contact_phone="+94771230001",
        height_cm=170,
        weight_kg=72.5,
        blood_type="B+",
    )
    grant_consent(patient)

    caregiver_user = ensure_user(
        email="demo.caregiver@careplus.local",
        role=Role.CAREGIVER,
        first_name="Lakmali",
        last_name="Herath",
    )
    caregiver = ensure_caregiver(
        caregiver_user,
        display_name="Lakmali Herath",
        city="Colombo",
        lon=COLOMBO[1] + 0.01,
        lat=COLOMBO[2] + 0.01,
        languages=["Sinhala", "English"],
        specialties=["diabetes", "hypertension", "elderly care", "wound care"],
        care_levels=["basic", "intermediate", "advanced"],
        trust_score=0.94,
        years_experience=11,
        bio="Colombo-based nurse-aide specialising in diabetes and elder care.",
        nic_id="198512345V",
    )
    grant_consent(caregiver_user)

    tamil_pt = ensure_user(
        email="demo.tamil@careplus.local",
        role=Role.PATIENT,
        first_name="Meena",
        last_name="Nadarajah",
    )
    complete_patient(
        tamil_pt,
        display_name="Meena Nadarajah",
        city="Jaffna",
        lon=JAFFNA[1],
        lat=JAFFNA[2],
        preferred_language="Tamil",
        languages=["Tamil", "English"],
        conditions=["dementia", "mobility support"],
        care_level="advanced",
        medications=["Donepezil"],
        emergency_contact_name="Arun Nadarajah",
        emergency_contact_phone="+94771230002",
        blood_type="A+",
    )
    grant_consent(tamil_pt)

    pay_pt = ensure_user(
        email="demo.pay@careplus.local",
        role=Role.PATIENT,
        first_name="Kumari",
        last_name="Perera",
    )
    complete_patient(
        pay_pt,
        display_name="Kumari Perera",
        city="Kandy",
        lon=SRI_LANKA_CITIES[4][1],
        lat=SRI_LANKA_CITIES[4][2],
        preferred_language="Sinhala",
        languages=["Sinhala"],
        conditions=["post-surgery"],
        care_level="intermediate",
        emergency_contact_name="Ruwan Perera",
        emergency_contact_phone="+94771230003",
    )
    grant_consent(pay_pt)

    failed_pt = ensure_user(
        email="demo.failed@careplus.local",
        role=Role.PATIENT,
        first_name="Ravi",
        last_name="Chandran",
    )
    complete_patient(
        failed_pt,
        display_name="Ravi Chandran",
        city="Batticaloa",
        lon=SRI_LANKA_CITIES[8][1],
        lat=SRI_LANKA_CITIES[8][2],
        preferred_language="Tamil",
        languages=["Tamil", "English"],
        conditions=["stroke recovery"],
        care_level="advanced",
        emergency_contact_name="Priya Chandran",
        emergency_contact_phone="+94771230004",
    )
    grant_consent(failed_pt)

    alumni = ensure_user(
        email="demo.alumni@careplus.local",
        role=Role.PATIENT,
        first_name="Malini",
        last_name="Silva",
    )
    complete_patient(
        alumni,
        display_name="Malini Silva",
        city="Galle",
        lon=SRI_LANKA_CITIES[5][1],
        lat=SRI_LANKA_CITIES[5][2],
        preferred_language="English",
        languages=["English", "Sinhala"],
        conditions=["elderly care"],
        care_level="basic",
        emergency_contact_name="Nimal Silva",
        emergency_contact_phone="+94771230005",
    )
    grant_consent(alumni)

    onboarding = ensure_user(
        email="demo.onboarding@careplus.local",
        role=Role.PATIENT,
        first_name="New",
        last_name="Patient",
    )
    PatientProfile.objects.update_or_create(
        user=onboarding,
        defaults={"display_name": "New Patient", "preferred_language": "English"},
    )

    pending_cg_user = ensure_user(
        email="demo.cg.pending@careplus.local",
        role=Role.CAREGIVER,
        first_name="Ishara",
        last_name="Mendis",
    )
    ensure_caregiver(
        pending_cg_user,
        display_name="Ishara Mendis",
        city="Negombo",
        lon=SRI_LANKA_CITIES[3][1],
        lat=SRI_LANKA_CITIES[3][2],
        languages=["Sinhala"],
        specialties=["pediatric support"],
        care_levels=["basic"],
        is_approved=False,
        is_active=False,
        is_available=False,
        trust_score=0.5,
        bio="Awaiting admin approval of certificates.",
        nic_id="",
        years_experience=None,
        certification_docs=[],
    )

    assert patient_profile_completion(patient.patient_profile).can_request_care

    _hire(
        patient=patient,
        caregiver=caregiver,
        message=f"{SHOWCASE} Need weekday diabetes support in Colombo.",
        pay=True,
        package_slug="intermediate-nursing",
    )
    rel = CareRelationship.objects.get(patient=patient, status=CareRelationshipStatus.ACTIVE)
    thread = get_or_create_thread_for_relationship(rel)
    send_message(
        thread=thread,
        sender=patient,
        body="Ayubowan Lakmali — can you come tomorrow after 8am? Glucose has been high.",
    )
    send_message(
        thread=thread,
        sender=caregiver_user,
        body="Ayubowan Sunil. Yes — I will arrive at 8:15 with the BP cuff. Please keep the logbook ready.",
    )
    send_message(
        thread=thread,
        sender=patient,
        body="Thank you. Also remind me about the evening Metformin.",
    )
    stats["messages"] = 3

    if ConditionTerm.objects.filter(slug="diabetes", active=True).exists():
        create_medical_record(
            patient=patient,
            condition_slug="diabetes",
            title="Type 2 diabetes — home plan",
            description="Morning glucose log, Metformin 500mg twice daily, low-sugar meals.",
            sensitive_notes="Family history of nephropathy. Prefers Sinhala explanations.",
        )
    if ConditionTerm.objects.filter(slug="hypertension", active=True).exists():
        create_medical_record(
            patient=patient,
            condition_slug="hypertension",
            title="Hypertension follow-up",
            description="Amlodipine 5mg. Target BP under 140/90.",
            sensitive_notes="Occasional dizziness on standing.",
        )
    stats["records"] = 2

    now = timezone.now()
    for hours_ago in range(20, 0, -2):
        ingest_metric(
            actor=patient,
            patient=patient,
            kind=HealthMetricKind.HEART_RATE,
            value=68 + (hours_ago % 7),
            unit="bpm",
            source="manual",
            recorded_at=now - timedelta(hours=hours_ago),
            metadata={"showcase": True},
        )
        ingest_metric(
            actor=patient,
            patient=patient,
            kind=HealthMetricKind.SPO2,
            value=97.0,
            unit="%",
            source="manual",
            recorded_at=now - timedelta(hours=hours_ago),
        )
    for minutes_ago in (25, 18, 10):
        ingest_metric(
            actor=patient,
            patient=patient,
            kind=HealthMetricKind.BLOOD_GLUCOSE,
            value=58.0,
            unit="mg/dL",
            source="glucometer",
            recorded_at=now - timedelta(minutes=minutes_ago),
        )
    ingest_metric(
        actor=patient,
        patient=patient,
        kind=HealthMetricKind.BLOOD_GLUCOSE,
        value=112.0,
        unit="mg/dL",
        source="glucometer",
        recorded_at=now - timedelta(hours=6),
    )
    emergency_run = create_match_run(
        user=patient,
        query="glucose dropped, need advanced caregiver nearby now",
        condition="diabetes",
        language="Sinhala",
        care_level="advanced",
        emergency=True,
        weights=[0.80, 0.05, 0.05, 0.10],
        latency_ms=42,
        source="demo_seed",
    )
    for rank, cg in enumerate(
        CaregiverProfile.objects.filter(is_active=True, is_approved=True)[:3],
        start=1,
    ):
        MatchResult.objects.create(
            run=emergency_run,
            caregiver=cg,
            rank=rank,
            score=round(0.92 - rank * 0.06, 3),
            cbf=0.7,
            cf=0.1,
            geo=0.85,
            trust=0.9,
            explanation="Matched because: strong medical/skill match.",
            distance_m=1200.0 * rank,
        )
    event = HealthEvent(
        patient=patient,
        event_type=HealthEventType.HEALTH_CRITICAL,
        kind=HealthMetricKind.BLOOD_GLUCOSE,
        rule_key="hypoglycemia_trend",
        severity="critical",
        window_start=now - timedelta(minutes=30),
        window_end=now,
        sample_count=3,
        rematch_run=emergency_run,
    )
    event.payload = {"showcase": True, "note": "Demo hypo cluster"}
    event.save()
    stats["health_events"] = 1

    routine_run = create_match_run(
        user=patient,
        query="I need a Sinhala caregiver for diabetes in Colombo",
        condition="diabetes",
        language="Sinhala",
        care_level="intermediate",
        emergency=False,
        weights=[0.48, 0.07, 0.2, 0.25],
        latency_ms=118,
        source="demo_seed",
    )
    for rank, cg in enumerate(
        CaregiverProfile.objects.filter(is_active=True, is_approved=True).order_by("-trust_score")[:5],
        start=1,
    ):
        MatchResult.objects.create(
            run=routine_run,
            caregiver=cg,
            rank=rank,
            score=round(0.88 - rank * 0.05, 3),
            cbf=0.62,
            cf=0.12,
            geo=0.7,
            trust=float(cg.trust_score),
            explanation="Matched because: highly rated by similar patients.",
            distance_m=800.0 * rank,
        )
    session = get_or_create_active_session(patient, lang="Sinhala")
    session.last_match_run = routine_run
    session.intent_chips = {
        "condition": "diabetes",
        "language": "Sinhala",
        "care_level": "intermediate",
    }
    session.turns = [
        {"role": "user", "text": "මට දියවැඩියාව තියෙනවා, Colombo caregiver ඕනේ", "route": "MATCH"},
        {
            "role": "serah",
            "text": "I found caregivers. Look at the cards and pick the best one.",
            "route": "MATCH",
        },
    ]
    session.save()
    create_voice_intent(
        user=patient,
        raw_text="I need a Sinhala caregiver for diabetes in Colombo",
        condition="diabetes",
        language="Sinhala",
        languages=["Sinhala", "English"],
        care_level="intermediate",
        urgency=Urgency.ROUTINE,
        source="seed",
    )
    create_voice_intent(
        user=patient,
        raw_text="My sugar dropped — this is urgent",
        condition="diabetes",
        language="English",
        care_level="advanced",
        urgency=Urgency.CRITICAL,
        source="seed",
    )

    create_care_request(
        patient=patient,
        caregiver=seed_cg(1),
        message=f"{SHOWCASE} Also considering a second opinion for night coverage.",
    )
    rejected = create_care_request(
        patient=patient,
        caregiver=seed_cg(2),
        message=f"{SHOWCASE} Weekend only please.",
    )
    reject_care_request(rejected, caregiver_user=seed_cg(2).user, reason="Fully booked this month.")
    cancelled = create_care_request(
        patient=patient,
        caregiver=seed_cg(3),
        message=f"{SHOWCASE} Might not need this — will cancel.",
    )
    cancel_care_request(cancelled, patient=patient)
    expired = create_care_request(
        patient=patient,
        caregiver=seed_cg(4),
        message=f"{SHOWCASE} Left unanswered past TTL.",
    )
    expired.status = CareRequestStatus.EXPIRED
    expired.expires_at = now - timedelta(days=1)
    expired.responded_at = now - timedelta(hours=2)
    expired.save(update_fields=["status", "expires_at", "responded_at", "updated_at"])
    stats["care_requests"] = 5

    tamil_cg = (
        CaregiverProfile.objects.filter(
            is_active=True, is_available=True, languages__contains=["Tamil"]
        )
        .exclude(pk=caregiver.pk)
        .first()
    )
    if tamil_cg is not None:
        create_care_request(
            patient=tamil_pt,
            caregiver=tamil_cg,
            message=f"{SHOWCASE} Jaffna dementia support, Tamil preferred.",
        )

    _hire(
        patient=pay_pt,
        caregiver=seed_cg(7),
        message=f"{SHOWCASE} Post-op Kandy — waiting to pay.",
        pay=False,
        package_slug="post-surgery-recovery",
    )
    _hire(
        patient=failed_pt,
        caregiver=seed_cg(8),
        message=f"{SHOWCASE} Stroke recovery — payment failed.",
        fail_pay=True,
        package_slug="advanced-clinical",
    )

    _ended_req, ended_rel, _, _ = _hire(
        patient=alumni,
        caregiver=seed_cg(5),
        message=f"{SHOWCASE} Completed a month of elder care in Galle.",
        pay=True,
        package_slug="basic-home-care",
    )
    end_relationship(ended_rel, actor=alumni, reason="Care period finished — family taking over.")
    Review.objects.create(
        relationship=ended_rel,
        patient=alumni,
        caregiver=seed_cg(5),
        rating=5,
        comment="Punctual and kind with Amma. Highly recommend.",
        status=ReviewStatus.APPROVED,
        moderator=admin,
        moderated_at=now,
    )
    _pending_rel_req, pending_rel, _, _ = _hire(
        patient=alumni,
        caregiver=seed_cg(6),
        message=f"{SHOWCASE} Short respite week — now ended, review pending.",
        pay=True,
        package_slug="night-respite",
    )
    end_relationship(pending_rel, actor=alumni, reason="Respite week complete.")
    Review.objects.create(
        relationship=pending_rel,
        patient=alumni,
        caregiver=seed_cg(6),
        rating=4,
        comment="Good overnight cover. Waiting on moderation.",
        status=ReviewStatus.PENDING,
    )

    for weekday in range(5):
        CaregiverAvailabilitySlot.objects.get_or_create(
            caregiver=caregiver,
            weekday=weekday,
            start_time=time(8, 0),
            end_time=time(16, 0),
            defaults={"timezone": "Asia/Colombo"},
        )
    Shift.objects.create(
        caregiver=caregiver,
        patient=patient,
        starts_at=now + timedelta(days=1, hours=2),
        ends_at=now + timedelta(days=1, hours=10),
        timezone="Asia/Colombo",
        status=ShiftStatus.BOOKED,
        notes=f"{SHOWCASE} Tomorrow diabetes check-in",
    )
    Shift.objects.create(
        caregiver=caregiver,
        patient=patient,
        starts_at=now - timedelta(days=3),
        ends_at=now - timedelta(days=3) + timedelta(hours=8),
        timezone="Asia/Colombo",
        status=ShiftStatus.CANCELLED,
        notes=f"{SHOWCASE} Cancelled — family took Amma to clinic",
    )

    Lead.objects.get_or_create(
        email="lead.new@example.lk",
        defaults={
            "name": "Chamari Fernando",
            "phone": "+94771239901",
            "message": "Need a Tamil-speaking caregiver in Batticaloa next week.",
            "city": "Batticaloa",
            "preferred_language": "Tamil",
            "source": "marketing_form",
            "status": LeadStatus.NEW,
            "ack_email_sent": True,
        },
    )
    Lead.objects.get_or_create(
        email="lead.contacted@example.lk",
        defaults={
            "name": "Pradeep Jayawardena",
            "phone": "+94771239902",
            "message": "Package pricing for advanced clinical in Colombo.",
            "city": "Colombo",
            "preferred_language": "English",
            "source": "marketing_form",
            "status": LeadStatus.CONTACTED,
            "contacted_at": now - timedelta(days=1),
            "contacted_by": admin,
            "admin_notes": "Sent catalog PDF.",
            "ack_email_sent": True,
        },
    )
    Lead.objects.get_or_create(
        email="lead.closed@example.lk",
        defaults={
            "name": "Sanduni Amarasinghe",
            "phone": "+94771239903",
            "message": "Hired through Serah — closing the enquiry.",
            "city": "Gampaha",
            "preferred_language": "Sinhala",
            "source": "marketing_form",
            "status": LeadStatus.CLOSED,
            "contacted_at": now - timedelta(days=4),
            "contacted_by": admin,
            "admin_notes": "Converted to demo.patient flow.",
            "ack_email_sent": True,
        },
    )

    stats["users"] = User.objects.filter(email__startswith="demo.").count()
    stats["relationships"] = CareRelationship.objects.filter(
        care_request__message__startswith=SHOWCASE
    ).count()
    return stats
