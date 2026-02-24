/**
 * External Services Module
 * 
 * Exports service management utilities for OpenCode and OpenClaw integration
 */

export * from './types';
export * from './LogRouter';
export * from './BaseService';
export * from './OpenCodeService';
export * from './OpenClawService';
export * from './ServiceManager';

// Re-export convenience functions
export {
  getServiceManager,
  initializeServices,
  cleanupServices,
} from './ServiceManager';
