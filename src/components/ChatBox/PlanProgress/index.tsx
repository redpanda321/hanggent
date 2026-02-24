/**
 * PlanProgress Component
 * 
 * Displays real-time plan execution progress with step tracking.
 * Receives updates via SSE events from PlanningFlow backend.
 * 
 * Features:
 * - Step-by-step progress visualization
 * - Expandable execution logs per step
 * - Summary view with "Show full output" toggle
 */

import React from 'react';
import { cn } from '@/lib/utils';
import { 
  CheckCircle2, 
  Circle, 
  Loader2, 
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ListTodo,
  Terminal,
  Eye,
  EyeOff,
  Wrench
} from 'lucide-react';
import { PlanData, PlanStepData, ExecutionLogEntry } from '@/store/chatStore';

// Re-export types for consumers
export type { PlanData, PlanStepData, ExecutionLogEntry };

interface PlanProgressProps {
  plan: PlanData;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
}

const stepStatusIcons: Record<PlanStepData['status'], React.ReactNode> = {
  not_started: <Circle className="w-4 h-4 text-gray-400" />,
  in_progress: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  blocked: <AlertCircle className="w-4 h-4 text-red-500" />,
};

const stepStatusColors: Record<PlanStepData['status'], string> = {
  not_started: 'bg-gray-100 border-gray-200 dark:bg-gray-800 dark:border-gray-700',
  in_progress: 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800',
  completed: 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800',
  blocked: 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800',
};

const logStatusColors: Record<ExecutionLogEntry['status'], string> = {
  running: 'text-blue-600 dark:text-blue-400',
  completed: 'text-green-600 dark:text-green-400',
  failed: 'text-red-600 dark:text-red-400',
};

const logStatusIcons: Record<ExecutionLogEntry['status'], React.ReactNode> = {
  running: <Loader2 className="w-3 h-3 animate-spin" />,
  completed: <CheckCircle2 className="w-3 h-3" />,
  failed: <AlertCircle className="w-3 h-3" />,
};

// ==================== Execution Log Entry Component ====================

function ExecutionLog({ log }: { log: ExecutionLogEntry }) {
  const [showFullOutput, setShowFullOutput] = React.useState(false);
  
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden">
      {/* Log header */}
      <div className="flex items-center justify-between px-2 py-1.5 bg-gray-50 dark:bg-gray-800/50">
        <div className="flex items-center gap-2">
          <Wrench className="w-3 h-3 text-gray-500" />
          <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
            {log.toolkit}
          </span>
          <span className="text-xs text-gray-500">→</span>
          <span className="text-xs text-gray-600 dark:text-gray-400">
            {log.method}
          </span>
        </div>
        <div className={cn("flex items-center gap-1", logStatusColors[log.status])}>
          {logStatusIcons[log.status]}
          <span className="text-xs capitalize">{log.status}</span>
        </div>
      </div>
      
      {/* Log content */}
      <div className="p-2 bg-white dark:bg-gray-900">
        {/* Summary */}
        <p className="text-xs text-gray-600 dark:text-gray-400">
          {log.summary}
        </p>
        
        {/* Full output toggle */}
        {log.full_output && (
          <>
            <button
              onClick={() => setShowFullOutput(!showFullOutput)}
              className="flex items-center gap-1 mt-2 text-xs text-blue-600 dark:text-blue-400 hover:underline"
            >
              {showFullOutput ? (
                <>
                  <EyeOff className="w-3 h-3" />
                  Hide full output
                </>
              ) : (
                <>
                  <Eye className="w-3 h-3" />
                  Show full output
                </>
              )}
            </button>
            
            {showFullOutput && (
              <pre className="mt-2 p-2 text-xs bg-gray-100 dark:bg-gray-800 rounded overflow-x-auto max-h-48 overflow-y-auto">
                <code className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {log.full_output}
                </code>
              </pre>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ==================== Plan Step Component ====================

function PlanStep({ step, isLast }: { step: PlanStepData; isLast: boolean }) {
  const [isExpanded, setIsExpanded] = React.useState(step.status === 'in_progress');
  
  // Auto-expand when step becomes active
  React.useEffect(() => {
    if (step.status === 'in_progress') {
      setIsExpanded(true);
    }
  }, [step.status]);

  const hasExpandableContent = step.description || step.result_preview || (step.execution_logs && step.execution_logs.length > 0);
  
  return (
    <div className="relative">
      {/* Vertical line connector */}
      {!isLast && (
        <div 
          className={cn(
            "absolute left-[9px] top-6 w-0.5 h-full -mb-2",
            step.status === 'completed' ? 'bg-green-300 dark:bg-green-700' : 'bg-gray-200 dark:bg-gray-700'
          )}
        />
      )}
      
      <div className={cn(
        "flex items-start gap-3 p-2 rounded-lg border transition-all",
        stepStatusColors[step.status]
      )}>
        <div className="flex-shrink-0 mt-0.5">
          {stepStatusIcons[step.status]}
        </div>
        
        <div className="flex-1 min-w-0">
          {/* Step header */}
          <div 
            className={cn(
              "flex items-center justify-between",
              hasExpandableContent && "cursor-pointer"
            )}
            onClick={() => hasExpandableContent && setIsExpanded(!isExpanded)}
          >
            <div className="flex items-center gap-2">
              <span className={cn(
                "text-xs font-medium px-1.5 py-0.5 rounded",
                step.status === 'in_progress' && "bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200",
                step.status === 'completed' && "bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-200",
                step.status === 'blocked' && "bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-200",
                step.status === 'not_started' && "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300",
              )}>
                Step {step.index + 1}
              </span>
              {step.agent_type && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  [{step.agent_type}]
                </span>
              )}
              {step.execution_logs && step.execution_logs.length > 0 && (
                <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <Terminal className="w-3 h-3" />
                  {step.execution_logs.length} {step.execution_logs.length === 1 ? 'log' : 'logs'}
                </span>
              )}
            </div>
            {hasExpandableContent && (
              <button className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded">
                {isExpanded ? (
                  <ChevronUp className="w-3 h-3 text-gray-500" />
                ) : (
                  <ChevronDown className="w-3 h-3 text-gray-500" />
                )}
              </button>
            )}
          </div>
          
          {/* Step title */}
          <p className={cn(
            "text-sm font-medium mt-1",
            step.status === 'in_progress' && "text-blue-700 dark:text-blue-300",
            step.status === 'completed' && "text-green-700 dark:text-green-300",
            step.status === 'blocked' && "text-red-700 dark:text-red-300",
            step.status === 'not_started' && "text-gray-700 dark:text-gray-300",
          )}>
            {step.title}
          </p>
          
          {/* Expanded content */}
          {isExpanded && hasExpandableContent && (
            <div className="mt-2 space-y-2">
              {/* Description */}
              {step.description && (
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  {step.description}
                </p>
              )}
              
              {/* Execution logs */}
              {step.execution_logs && step.execution_logs.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1">
                    <Terminal className="w-3 h-3" />
                    Execution Logs
                  </p>
                  {step.execution_logs.map((log, idx) => (
                    <ExecutionLog key={idx} log={log} />
                  ))}
                </div>
              )}
              
              {/* Result preview */}
              {step.result_preview && step.status === 'completed' && (
                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                  <p className="font-medium text-xs text-gray-700 dark:text-gray-300 mb-1">Result:</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap line-clamp-3">
                    {step.result_preview}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProgressBar({ completed, total }: { completed: number; total: number }) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
  
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div 
          className="h-full bg-green-500 dark:bg-green-600 transition-all duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-600 dark:text-gray-400 tabular-nums">
        {completed}/{total}
      </span>
    </div>
  );
}

export function PlanProgress({ 
  plan, 
  isCollapsed = false, 
  onToggleCollapse,
  className 
}: PlanProgressProps) {
  const isCompleted = plan.status === 'completed';
  const isFailed = plan.status === 'failed';
  
  return (
    <div className={cn(
      "rounded-lg border bg-white dark:bg-gray-900 shadow-sm",
      isCompleted && "border-green-300 dark:border-green-700",
      isFailed && "border-red-300 dark:border-red-700",
      !isCompleted && !isFailed && "border-gray-200 dark:border-gray-700",
      className
    )}>
      {/* Header */}
      <div 
        className={cn(
          "flex items-center justify-between p-3 cursor-pointer",
          "border-b border-gray-100 dark:border-gray-800"
        )}
        onClick={onToggleCollapse}
      >
        <div className="flex items-center gap-2">
          <ListTodo className={cn(
            "w-5 h-5",
            isCompleted && "text-green-500",
            isFailed && "text-red-500",
            !isCompleted && !isFailed && "text-blue-500"
          )} />
          <div>
            <h3 className="font-medium text-sm text-gray-900 dark:text-gray-100">
              {plan.title || 'Execution Plan'}
            </h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={cn(
                "text-xs px-1.5 py-0.5 rounded font-medium",
                plan.status === 'created' && "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
                plan.status === 'running' && "bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200",
                plan.status === 'completed' && "bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-200",
                plan.status === 'failed' && "bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-200",
                plan.status === 'paused' && "bg-yellow-100 text-yellow-700 dark:bg-yellow-800 dark:text-yellow-200",
              )}>
                {plan.status ? plan.status.charAt(0).toUpperCase() + plan.status.slice(1) : 'Unknown'}
              </span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="w-24">
            <ProgressBar completed={plan.completed_steps} total={plan.total_steps} />
          </div>
          <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            {isCollapsed ? (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronUp className="w-4 h-4 text-gray-500" />
            )}
          </button>
        </div>
      </div>
      
      {/* Steps List */}
      {!isCollapsed && (
        <div className="p-3 space-y-2">
          {plan.steps.map((step, index) => (
            <PlanStep 
              key={`${plan.plan_id}-step-${step.index}`}
              step={step}
              isLast={index === plan.steps.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default PlanProgress;
