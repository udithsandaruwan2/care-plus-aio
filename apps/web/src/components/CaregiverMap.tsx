import { useEffect, useMemo } from 'react';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { CaregiverProfile } from '@care-plus/api-client';
import 'leaflet/dist/leaflet.css';

const SL_CENTER: [number, number] = [7.8, 80.7];

const pinIcon = L.divIcon({
  className: '',
  html: `<span style="
    display:block;width:14px;height:14px;border-radius:9999px;
    background:#5eead4;border:2px solid #0f172a;box-shadow:0 0 0 2px #5eead466;
  "></span>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) {
      map.setView(SL_CENTER, 7);
      return;
    }
    if (points.length === 1) {
      map.setView(points[0], 11);
      return;
    }
    map.fitBounds(L.latLngBounds(points), { padding: [28, 28], maxZoom: 12 });
  }, [map, points]);
  return null;
}

export function CaregiverMap({
  caregivers,
  selectedId,
  onSelect,
}: {
  caregivers: CaregiverProfile[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const points = useMemo(
    () =>
      caregivers
        .filter((c) => c.latitude != null && c.longitude != null)
        .map((c) => [c.latitude as number, c.longitude as number] as [number, number]),
    [caregivers],
  );

  return (
    <div className="h-72 w-full overflow-hidden rounded-2xl border border-hair sm:h-96">
      <MapContainer
        center={SL_CENTER}
        zoom={7}
        className="h-full w-full bg-void"
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <FitBounds points={points} />
        {caregivers.map((cg) => {
          if (cg.latitude == null || cg.longitude == null) return null;
          const selected = cg.id === selectedId;
          return (
            <Marker
              key={cg.id}
              position={[cg.latitude, cg.longitude]}
              icon={
                selected
                  ? L.divIcon({
                      className: '',
                      html: `<span style="
                        display:block;width:18px;height:18px;border-radius:9999px;
                        background:#22d3ee;border:2px solid #ecfeff;box-shadow:0 0 12px #22d3eeaa;
                      "></span>`,
                      iconSize: [18, 18],
                      iconAnchor: [9, 9],
                    })
                  : pinIcon
              }
              eventHandlers={{ click: () => onSelect(cg.id) }}
            >
              <Popup>
                <strong>{cg.display_name}</strong>
                <br />
                {(cg.specialties || []).slice(0, 3).join(' · ') || 'General care'}
                {cg.city ? ` · ${cg.city}` : ''}
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
