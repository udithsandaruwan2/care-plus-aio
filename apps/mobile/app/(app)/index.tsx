import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link, router } from 'expo-router';
import { brand, colors } from '@care-plus/ui-tokens';
import { t } from '@care-plus/core';
import { useAuth } from '../../src/auth/AuthContext';

type HubLink = { title: string; desc: string; note?: string; href?: string };

function linksForRole(role: string): HubLink[] {
  if (role === 'patient') {
    return [
      {
        title: t('en', 'hub.serahTitle'),
        desc: t('en', 'hub.serahDesc'),
        href: '/(app)/serah',
      },
      {
        title: t('en', 'hub.requestsTitle'),
        desc: t('en', 'hub.requestsDesc'),
        href: '/(app)/requests',
      },
      { title: t('en', 'hub.messagesTitle'), desc: t('en', 'hub.messagesDesc') },
      { title: t('en', 'hub.scheduleTitle'), desc: t('en', 'hub.scheduleDesc') },
      { title: t('en', 'hub.recordsTitle'), desc: t('en', 'hub.recordsDesc') },
      { title: t('en', 'hub.accountTitle'), desc: t('en', 'hub.accountDesc') },
    ];
  }
  if (role === 'caregiver') {
    return [
      {
        title: t('en', 'hub.inboxTitle'),
        desc: t('en', 'hub.requestsDesc'),
        href: '/(app)/requests',
      },
      { title: t('en', 'hub.messagesTitle'), desc: t('en', 'hub.messagesDesc') },
      { title: t('en', 'hub.scheduleTitle'), desc: t('en', 'hub.scheduleDesc') },
      { title: t('en', 'hub.accountTitle'), desc: t('en', 'hub.accountDesc') },
    ];
  }
  // admin / auditor — full admin console stays on web
  return [
    {
      title: t('en', 'hub.analyticsTitle'),
      desc: t('en', 'hub.analyticsDesc'),
      note: 'Use the web admin console for full tools',
    },
    { title: t('en', 'hub.auditTitle'), desc: t('en', 'hub.auditDesc') },
    { title: t('en', 'hub.usersTitle'), desc: t('en', 'hub.usersDescAdmin') },
  ];
}

export default function HubScreen() {
  const { user, logout } = useAuth();
  if (!user) return null;

  const name = user.first_name?.trim() || user.email.split('@')[0];
  const links = linksForRole(user.role);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>{t('en', 'hub.eyebrow')}</Text>
      <Text style={styles.title}>{t('en', 'hub.welcome', { name })}</Text>
      <Text style={styles.subtitle}>{t('en', 'hub.subtitle')}</Text>

      <View style={styles.badge}>
        <Text style={styles.badgeText}>{user.role}</Text>
        <Text style={styles.badgeEmail}>{user.email}</Text>
      </View>

      {user.role === 'patient' && (
        <Text style={styles.hint}>
          {t('en', 'hub.patientProfileHint', { percent: '—' })}
        </Text>
      )}
      {user.role === 'caregiver' && (
        <Text style={styles.hint}>
          {t('en', 'hub.caregiverProfileHint', { percent: '—' })}
        </Text>
      )}

      <Text style={styles.section}>{t('en', 'hub.quickActions')}</Text>
      {links.map((item) =>
        item.href ? (
          <Link key={item.title} href={item.href as '/(app)/serah' | '/(app)/requests'} asChild>
            <Pressable style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
              <Text style={styles.cardTitle}>{item.title}</Text>
              <Text style={styles.cardDesc}>{item.desc}</Text>
              {item.note ? <Text style={styles.note}>{item.note}</Text> : null}
            </Pressable>
          </Link>
        ) : (
          <View key={item.title} style={styles.card}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardDesc}>{item.desc}</Text>
            {item.note ? <Text style={styles.note}>{item.note}</Text> : null}
          </View>
        ),
      )}

      <Link href="/(app)/status" style={styles.statusLink}>
        API status · health check
      </Link>

      <Pressable
        onPress={() => {
          void logout().then(() => router.replace('/(auth)/login'));
        }}
        style={({ pressed }) => [styles.signOut, pressed && styles.pressed]}
      >
        <Text style={styles.signOutText}>{t('en', 'action.signOut')}</Text>
      </Pressable>

      <Text style={styles.footer}>
        {brand.name} · Step 65 match + request · {user.role}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 40,
  },
  eyebrow: {
    color: colors.accentCyan,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    marginTop: 8,
    color: colors.textPrimary,
    fontSize: 26,
    fontWeight: '700',
  },
  subtitle: {
    marginTop: 8,
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  badge: {
    marginTop: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: 'rgba(18, 22, 34, 0.85)',
    padding: 12,
    gap: 4,
  },
  badgeText: {
    color: colors.accentViolet,
    fontWeight: '700',
    textTransform: 'capitalize',
    fontSize: 13,
  },
  badgeEmail: {
    color: colors.textMuted,
    fontSize: 13,
  },
  hint: {
    marginTop: 12,
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  section: {
    marginTop: 24,
    marginBottom: 10,
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '600',
  },
  card: {
    marginBottom: 10,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: 'rgba(18, 22, 34, 0.85)',
    padding: 14,
    gap: 4,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontWeight: '600',
    fontSize: 15,
  },
  cardDesc: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  note: {
    marginTop: 4,
    color: colors.accentAmber,
    fontSize: 12,
  },
  statusLink: {
    marginTop: 16,
    color: colors.accentMint,
    fontSize: 13,
    fontWeight: '600',
  },
  signOut: {
    marginTop: 24,
    alignSelf: 'flex-start',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(251, 113, 133, 0.45)',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  pressed: {
    opacity: 0.8,
  },
  signOutText: {
    color: colors.accentRose,
    fontWeight: '600',
    fontSize: 13,
  },
  footer: {
    marginTop: 28,
    color: colors.textMuted,
    fontSize: 12,
  },
});
