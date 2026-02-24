// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

import Terminal from '@/components/Terminal';
import useChatStoreAdapter from '@/hooks/useChatStoreAdapter';
import {
  Bot,
  ChevronLeft,
  Code2,
  FileCode,
  Settings2,
  TerminalSquare,
} from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';

type TabId = 'terminal' | 'files';

export default function OpenCodeWorkSpace() {
  const { chatStore } = useChatStoreAdapter();
  const { t } = useTranslation();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<TabId>('terminal');

  const activeTaskId = chatStore?.activeTaskId;
  const taskAssigning = chatStore?.tasks[activeTaskId as string]?.taskAssigning;
  const activeWorkSpace =
    chatStore?.tasks[activeTaskId as string]?.activeWorkSpace;

  const activeAgent = useMemo(() => {
    if (!chatStore || !taskAssigning) return null;
    return (
      taskAssigning.find((item) => item.agent_id === activeWorkSpace) || null
    );
  }, [chatStore, taskAssigning, activeWorkSpace]);

  if (!chatStore) {
    return <div>Loading...</div>;
  }

  // Collect terminal content across all tasks
  const terminalTasks =
    activeAgent?.tasks.filter(
      (task) => task?.terminal && task.terminal.length > 0
    ) ?? [];

  // Collect file changes from task toolkits that relate to write/edit
  const fileChanges =
    activeAgent?.tasks.flatMap((task) =>
      (task.toolkits ?? [])
        .filter(
          (tk) =>
            tk.toolkitName?.toLowerCase().includes('write') ||
            tk.toolkitName?.toLowerCase().includes('edit') ||
            tk.toolkitName?.toLowerCase().includes('file')
        )
        .map((tk) => ({
          taskId: task.id,
          toolkitName: tk.toolkitName,
          message: tk.message,
          status: tk.toolkitStatus,
        }))
    ) ?? [];

  const tabs: { id: TabId; label: string; icon: React.ReactNode; count?: number }[] = [
    {
      id: 'terminal',
      label: t('workspace.terminal', 'Terminal'),
      icon: <TerminalSquare size={14} />,
      count: terminalTasks.length,
    },
    {
      id: 'files',
      label: t('workspace.files', 'Files'),
      icon: <FileCode size={14} />,
      count: fileChanges.length,
    },
  ];

  return (
    <div className="flex h-[calc(100vh-104px)] w-full flex-1 items-center justify-center transition-all duration-300 ease-in-out">
      <div className="relative flex h-full w-full flex-col overflow-hidden rounded-2xl bg-menutabs-bg-default">
        {/* Header */}
        <div className="flex flex-shrink-0 items-center justify-between rounded-t-2xl px-2 pb-2 pt-3">
          <div className="flex items-center justify-start gap-sm">
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                chatStore.setActiveWorkSpace(
                  chatStore.activeTaskId as string,
                  'workflow'
                );
              }}
            >
              <ChevronLeft size={16} />
            </Button>
            <div className="flex h-[26px] items-center gap-xs rounded-lg bg-cyan-200 px-2 py-0.5">
              <Bot className="h-4 w-4 text-icon-primary" />
              <Code2 className="h-3 w-3 text-cyan-700" />
              <div className="text-[10px] font-bold leading-17 text-cyan-700">
                OpenCode Agent
              </div>
            </div>
            <div className="text-[10px] font-medium leading-17 text-text-tertiary">
              {
                activeAgent?.tasks?.filter(
                  (task) => task.status && task.status !== 'running'
                ).length
              }
              /{activeAgent?.tasks?.length}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Tab switcher */}
            <div className="flex items-center gap-0.5 rounded-lg border border-solid border-border-primary bg-transparent p-0.5">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-bg-fill-primary text-text-inverse-primary'
                      : 'text-text-tertiary hover:text-text-primary'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className="ml-0.5 rounded-full bg-cyan-100 px-1 text-[9px] text-cyan-700">
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>
            <Button size="icon" variant="ghost">
              <Settings2 size={16} />
            </Button>
          </div>
        </div>

        {/* Content area */}
        <div className="min-h-0 flex-1">
          {/* Terminal tab */}
          {activeTab === 'terminal' && (
            <>
              {terminalTasks.length === 0 ? (
                <div className="flex h-full w-full items-center justify-center text-sm text-text-tertiary">
                  {t(
                    'workspace.no-terminal',
                    'No terminal output yet — OpenCode agent is getting started...'
                  )}
                </div>
              ) : terminalTasks.length === 1 ? (
                <div className="h-full w-full rounded-b-2xl pt-sm">
                  <Terminal
                    instanceId={activeAgent?.activeWebviewIds?.[0]?.id}
                    content={terminalTasks[0].terminal}
                  />
                </div>
              ) : (
                <div
                  ref={scrollContainerRef}
                  className="scrollbar relative flex min-h-0 flex-1 flex-wrap justify-start gap-4 overflow-y-auto px-2 pb-2"
                >
                  {terminalTasks.map((task) => (
                    <div
                      key={task.id}
                      className="group relative h-[calc(50%-8px)] w-[calc(50%-8px)] cursor-pointer rounded-lg"
                    >
                      <Terminal instanceId={task.id} content={task.terminal} />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Files tab */}
          {activeTab === 'files' && (
            <div className="scrollbar flex h-full flex-col gap-1 overflow-y-auto p-2">
              {fileChanges.length === 0 ? (
                <div className="flex h-full w-full items-center justify-center text-sm text-text-tertiary">
                  {t('workspace.no-files', 'No file changes yet')}
                </div>
              ) : (
                fileChanges.map((change, idx) => (
                  <div
                    key={`${change.taskId}-${idx}`}
                    className="flex items-start gap-2 rounded-lg border border-solid border-border-primary bg-surface-secondary p-2"
                  >
                    <FileCode size={14} className="mt-0.5 flex-shrink-0 text-cyan-600" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-text-primary">
                        {change.toolkitName}
                      </div>
                      {change.message && (
                        <div className="mt-0.5 truncate text-[10px] text-text-tertiary">
                          {change.message}
                        </div>
                      )}
                    </div>
                    {change.status && (
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                          change.status === 'running'
                            ? 'bg-amber-100 text-amber-700'
                            : change.status === 'completed'
                              ? 'bg-emerald-100 text-emerald-700'
                              : change.status === 'failed'
                                ? 'bg-red-100 text-red-700'
                                : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {change.status === 'running'
                          ? 'In progress'
                          : change.status === 'completed'
                            ? 'Done'
                            : change.status === 'failed'
                              ? 'Failed'
                              : 'Pending'}
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
