/**
 * PlanHistorySidebar Component
 * 
 * Sidebar for viewing plan history with filtering by project and status.
 * Allows users to browse, filter, and resume past plans.
 */

import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  ListTodo,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  Play,
  Filter,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { usePlanHistory, PlanStatusFilter } from '@/hooks/usePlanHistory';
import { PlanData } from '@/store/chatStore';
import { useTranslation } from 'react-i18next';
import useChatStoreAdapter from '@/hooks/useChatStoreAdapter';

interface PlanHistorySidebarProps {
  isOpen: boolean;
  onClose: () => void;
  showAllProjects?: boolean;
  onToggleShowAllProjects?: () => void;
}

// Status filter options
const STATUS_FILTERS: { value: PlanStatusFilter; label: string }[] = [
  { value: 'all', label: 'All Plans' },
  { value: 'completed', label: 'Completed' },
  { value: 'incomplete', label: 'In Progress' },
  { value: 'failed', label: 'Failed' },
];

// Plan status icons and colors
const planStatusConfig: Record<PlanData['status'], { icon: React.ReactNode; color: string; bgColor: string }> = {
  created: {
    icon: <Clock className="w-4 h-4" />,
    color: 'text-gray-500',
    bgColor: 'bg-gray-100 dark:bg-gray-800',
  },
  running: {
    icon: <Play className="w-4 h-4" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
  },
  paused: {
    icon: <Clock className="w-4 h-4" />,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
  },
  completed: {
    icon: <CheckCircle2 className="w-4 h-4" />,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
  },
  failed: {
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
  },
};

// Plan Item Component
function PlanItem({ 
  plan, 
  onClick,
  isExpanded,
  onToggleExpand,
}: { 
  plan: PlanData; 
  onClick: () => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}) {
  const config = planStatusConfig[plan.status];
  const progressPercent = plan.total_steps > 0 
    ? Math.round((plan.completed_steps / plan.total_steps) * 100) 
    : 0;

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      {/* Plan Header */}
      <div
        className={cn(
          "flex items-center gap-3 p-3 cursor-pointer transition-colors",
          "hover:bg-gray-50 dark:hover:bg-gray-800/50",
          config.bgColor
        )}
        onClick={onToggleExpand}
      >
        {/* Expand/Collapse */}
        <button className="flex-shrink-0">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </button>
        
        {/* Status Icon */}
        <div className={cn("flex-shrink-0", config.color)}>
          {config.icon}
        </div>
        
        {/* Plan Info */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {plan.title || 'Untitled Plan'}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <span className={cn("text-xs capitalize", config.color)}>
              {plan.status}
            </span>
            <span className="text-xs text-gray-400">•</span>
            <span className="text-xs text-gray-500">
              {plan.completed_steps}/{plan.total_steps} steps
            </span>
          </div>
        </div>
        
        {/* Progress Bar */}
        <div className="w-16 flex-shrink-0">
          <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full transition-all duration-300",
                plan.status === 'completed' && "bg-green-500",
                plan.status === 'failed' && "bg-red-500",
                plan.status !== 'completed' && plan.status !== 'failed' && "bg-blue-500"
              )}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </div>
      
      {/* Expanded Steps */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-gray-200 dark:border-gray-700"
          >
            <div className="p-3 bg-white dark:bg-gray-900 space-y-2">
              {plan.steps.slice(0, 5).map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs">
                  <span className={cn(
                    "w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-medium",
                    step.status === 'completed' && "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-400",
                    step.status === 'in_progress' && "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400",
                    step.status === 'blocked' && "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-400",
                    step.status === 'not_started' && "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
                  )}>
                    {idx + 1}
                  </span>
                  <span className="text-gray-600 dark:text-gray-400 truncate flex-1">
                    {step.title}
                  </span>
                </div>
              ))}
              {plan.steps.length > 5 && (
                <p className="text-xs text-gray-400 pl-7">
                  +{plan.steps.length - 5} more steps
                </p>
              )}
              
              {/* Resume Button for incomplete plans */}
              {(plan.status === 'created' || plan.status === 'running' || plan.status === 'paused') && (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full mt-2"
                  onClick={(e) => {
                    e.stopPropagation();
                    onClick();
                  }}
                >
                  <Play className="w-3 h-3 mr-1" />
                  Resume Plan
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Status Filter Dropdown
function StatusFilterDropdown({ 
  value, 
  onChange 
}: { 
  value: PlanStatusFilter; 
  onChange: (filter: PlanStatusFilter) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const currentFilter = STATUS_FILTERS.find(f => f.value === value);

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        className="w-full justify-between"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <Filter className="w-3 h-3" />
          <span>{currentFilter?.label || 'All Plans'}</span>
        </div>
        <ChevronDown className={cn("w-3 h-3 transition-transform", isOpen && "rotate-180")} />
      </Button>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-10"
          >
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                className={cn(
                  "w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-800",
                  value === filter.value && "bg-gray-100 dark:bg-gray-800"
                )}
                onClick={() => {
                  onChange(filter.value);
                  setIsOpen(false);
                }}
              >
                {filter.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Main Component
export default function PlanHistorySidebar({ 
  isOpen, 
  onClose,
  showAllProjects = false,
  onToggleShowAllProjects,
}: PlanHistorySidebarProps) {
  const { t } = useTranslation();
  const { projectStore } = useChatStoreAdapter();
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);
  
  const {
    plans,
    isLoading,
    totalPlans,
    totalPages,
    currentPage,
    statusFilter,
    setStatusFilter,
    setPage,
  } = usePlanHistory({
    projectId: projectStore?.activeProjectId,
    showAllProjects,
  });

  const handlePlanClick = (plan: PlanData) => {
    // TODO: Implement plan resume/navigation
    console.log('Plan clicked:', plan);
  };

  const toggleExpand = (planId: string) => {
    setExpandedPlanId(prev => prev === planId ? null : planId);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40"
            onClick={onClose}
          />
          
          {/* Sidebar Panel */}
          <motion.div
            initial={{ x: -320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -320, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed left-0 top-0 bottom-0 w-80 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 shadow-xl z-50 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <ListTodo className="w-5 h-5 text-blue-500" />
                <h2 className="font-semibold text-gray-900 dark:text-gray-100">
                  Plan History
                </h2>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
              >
                <ArrowLeft className="w-4 h-4" />
              </Button>
            </div>
            
            {/* Filters */}
            <div className="p-4 space-y-3 border-b border-gray-200 dark:border-gray-700">
              <StatusFilterDropdown
                value={statusFilter}
                onChange={setStatusFilter}
              />
              
              {onToggleShowAllProjects && (
                <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showAllProjects}
                    onChange={onToggleShowAllProjects}
                    className="rounded border-gray-300 dark:border-gray-600"
                  />
                  Show all projects
                </label>
              )}
            </div>
            
            {/* Plans List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
                </div>
              ) : plans.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  <ListTodo className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No plans found</p>
                </div>
              ) : (
                plans.map((plan) => (
                  <PlanItem
                    key={plan.plan_id}
                    plan={plan}
                    onClick={() => handlePlanClick(plan)}
                    isExpanded={expandedPlanId === plan.plan_id}
                    onToggleExpand={() => toggleExpand(plan.plan_id)}
                  />
                ))
              )}
            </div>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage <= 1}
                  onClick={() => setPage(currentPage - 1)}
                >
                  Previous
                </Button>
                <span className="text-sm text-gray-500">
                  {currentPage} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage >= totalPages}
                  onClick={() => setPage(currentPage + 1)}
                >
                  Next
                </Button>
              </div>
            )}
            
            {/* Total count */}
            <div className="px-4 pb-4 text-xs text-gray-400 text-center">
              {totalPlans} plan{totalPlans !== 1 ? 's' : ''} total
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
