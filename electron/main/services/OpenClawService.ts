/**
 * OpenClawService - Manages the OpenClaw messaging gateway service
 */

import { ServiceConfig } from './types';
import { BaseService } from './BaseService';
import { LogRouter } from './LogRouter';

export class OpenClawService extends BaseService {
  constructor(config: ServiceConfig, logRouter: LogRouter) {
    super('openclaw', config, logRouter);
  }

  /**
   * Override spawn to use OpenClaw-specific startup
   */
  protected async spawnProcess(): Promise<void> {
    // OpenClaw uses 'openclaw gateway' to start the gateway server
    const originalArgs = this.config.args;
    
    // If args is empty or just ['gateway'], use default
    if (!originalArgs.length || originalArgs[0] === 'gateway') {
      this.config.args = ['gateway'];
    }

    await super.spawnProcess();
    
    // Restore original args
    this.config.args = originalArgs;
  }

  /**
   * Get OpenClaw-specific API endpoints
   */
  getApiEndpoints() {
    const baseUrl = this.getUrl();
    return {
      health: `${baseUrl}/health`,
      channels: `${baseUrl}/channels`,
      messages: `${baseUrl}/messages`,
      pairing: `${baseUrl}/pairing`,
      websocket: `${baseUrl.replace('http', 'ws')}/ws`,
    };
  }

  /**
   * Get available messaging channels
   */
  async getChannels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.getUrl()}/channels`);
      if (response.ok) {
        const data = await response.json();
        return data.channels || [];
      }
    } catch (error) {
      // Service might not be running
    }
    return [];
  }

  /**
   * Get MCP server configuration for OpenClaw
   */
  getMcpConfig(): { command: string; args: string[] } {
    return {
      command: this.config.command,
      args: ['mcp'],
    };
  }

  /**
   * Send a message via OpenClaw
   */
  async sendMessage(channel: string, to: string, message: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.getUrl()}/messages/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, to, message }),
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  }
}
