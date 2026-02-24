/**
 * OpenCodeService - Manages the OpenCode coding agent service
 */

import { ServiceConfig } from './types';
import { BaseService } from './BaseService';
import { LogRouter } from './LogRouter';

export class OpenCodeService extends BaseService {
  constructor(config: ServiceConfig, logRouter: LogRouter) {
    super('opencode', config, logRouter);
  }

  /**
   * Override spawn to use OpenCode-specific startup
   */
  protected async spawnProcess(): Promise<void> {
    // OpenCode uses 'opencode serve' or just 'opencode' to start
    // Adjust args based on how opencode CLI works
    const originalArgs = this.config.args;
    
    // If args is empty or just ['serve'], use default
    if (!originalArgs.length || originalArgs[0] === 'serve') {
      this.config.args = ['serve'];
    }

    await super.spawnProcess();
    
    // Restore original args
    this.config.args = originalArgs;
  }

  /**
   * Get OpenCode-specific API endpoints
   */
  getApiEndpoints() {
    const baseUrl = this.getUrl();
    return {
      health: `${baseUrl}/health`,
      session: `${baseUrl}/session`,
      project: `${baseUrl}/project`,
      file: `${baseUrl}/file`,
      events: `${baseUrl}/events`,
    };
  }

  /**
   * Check if OpenCode supports MCP
   */
  async checkMcpSupport(): Promise<boolean> {
    try {
      const response = await fetch(`${this.getUrl()}/mcp/tools`);
      return response.ok;
    } catch {
      return false;
    }
  }
}
