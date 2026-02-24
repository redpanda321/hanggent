import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.hanggent.app',
  appName: 'Hanggent',
  webDir: 'dist-web',
  server: {
    // Allow loading from localhost during development
    androidScheme: 'https',
    iosScheme: 'https',
  },
  plugins: {
    // Splash screen configuration
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#000000',
      showSpinner: false,
    },
  },
  ios: {
    contentInset: 'automatic',
    preferredContentMode: 'mobile',
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
