import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { colors } from '@care-plus/ui-tokens';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bgVoid },
          headerTintColor: colors.textPrimary,
          headerTitleStyle: { fontWeight: '600' },
          contentStyle: { backgroundColor: colors.bgVoid },
        }}
      />
    </>
  );
}
