import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Redirect, Stack } from 'expo-router';
import { colors } from '@care-plus/ui-tokens';
import { useAuth } from '../../src/auth/AuthContext';

export default function AppLayout() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={styles.screen}>
        <ActivityIndicator color={colors.accentCyan} size="large" />
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/(auth)/login" />;
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.bgVoid },
        headerTintColor: colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.bgVoid },
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Care Plus' }} />
      <Stack.Screen name="serah" options={{ title: 'Serah' }} />
      <Stack.Screen name="requests" options={{ title: 'Requests' }} />
      <Stack.Screen name="status" options={{ title: 'API status' }} />
    </Stack>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
