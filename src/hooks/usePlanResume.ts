/**
 * usePlanResume Hook
 * 
 * Fetches incomplete plans on page load and provides state for the resume dialog.
 * Plans can be in CREATED, RUNNING, or PAUSED status.
 */

import { useState, useEffect, useCallback } from 'react';
import { proxyFetchGet, proxyFetchPut } from '@/api/http';
import { PlanData } from '@/store/chatStore';
import { useAuthStore } from '@/store/authStore';

interface IncompletePlan {
  id: number;
  user_id: number;
  project_id: string;
  task_id: string;
  plan_id: string;
  title: string;
  status: number;
  steps: Array<{
    index: number;
    title: string;
    description?: string;
    agent_type?: string;
    status: number;
  }>;
  current_step_index: number;
  total_steps: number;
  completed_steps: number;
  created_at?: string;
  updated_at?: string;
}

// Plan status enum values (from backend)
const PLAN_STATUS = {
  CREATED: 1,
  RUNNING: 2,
  PAUSED: 3,
  COMPLETED: 4,
  FAILED: 5,
} as const;

// Step status enum values (from backend)
const STEP_STATUS = {
  NOT_STARTED: 0,
  IN_PROGRESS: 1,
  COMPLETED: 2,
  BLOCKED: 3,
} as const;

// Map backend status int to frontend status string
function mapPlanStatus(status: number): PlanData['status'] {
  switch (status) {
    case PLAN_STATUS.CREATED:
      return 'created';
    case PLAN_STATUS.RUNNING:
      return 'running';
    case PLAN_STATUS.PAUSED:
      return 'paused';
    case PLAN_STATUS.COMPLETED:
      return 'completed';
    case PLAN_STATUS.FAILED:
      return 'failed';
    default:
      return 'created';
  }
}

function mapStepStatus(status: number): 'not_started' | 'in_progress' | 'completed' | 'blocked' {
  switch (status) {
    case STEP_STATUS.NOT_STARTED:
      return 'not_started';
    case STEP_STATUS.IN_PROGRESS:
      return 'in_progress';
    case STEP_STATUS.COMPLETED:
      return 'completed';
    case STEP_STATUS.BLOCKED:
      return 'blocked';
    default:
      return 'not_started';
  }
}

// Convert backend plan to frontend PlanData format
function convertToPlanData(plan: IncompletePlan): PlanData {
  return {
    plan_id: plan.plan_id,
    title: plan.title,
    total_steps: plan.total_steps,
    completed_steps: plan.completed_steps,
    status: mapPlanStatus(plan.status),
    steps: plan.steps.map((step) => ({
      index: step.index,
      title: step.title,
      description: step.description,
      agent_type: step.agent_type,
      status: mapStepStatus(step.status),
    })),
    // Extended fields for resume
    db_id: plan.id,
    project_id: plan.project_id,
    task_id: plan.task_id,
    current_step_index: plan.current_step_index,
  };
}

export interface UsePlanResumeResult {
  incompletePlans: PlanData[];
  currentPlan: PlanData | null;
  isLoading: boolean;
  error: string | null;
  showResumeDialog: boolean;
  setShowResumeDialog: (show: boolean) => void;
  handleResume: (plan: PlanData) => Promise<void>;
  handleDismiss: () => void;
  refetch: () => Promise<void>;
}

export function usePlanResume(projectId?: string | null): UsePlanResumeResult {
  const token = useAuthStore((s) => s.token);
  const [incompletePlans, setIncompletePlans] = useState<PlanData[]>([]);
  const [currentPlan, setCurrentPlan] = useState<PlanData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showResumeDialog, setShowResumeDialog] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);

  const fetchIncompletePlans = useCallback(async () => {
    if (!token) {
      setIncompletePlans([]);
      setCurrentPlan(null);
      setShowResumeDialog(false);
      setIsLoading(false);
      setError(null);
      setHasFetched(true);
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      const response = await proxyFetchGet('/api/plan/incomplete');
      const plans: IncompletePlan[] = Array.isArray(response) ? response : [];
      
      // Convert to PlanData format
      const convertedPlans = plans.map(convertToPlanData);
      setIncompletePlans(convertedPlans);
      
      // Filter by project if specified
      let relevantPlans = convertedPlans;
      if (projectId) {
        relevantPlans = convertedPlans.filter((p) => p.project_id === projectId);
      }
      
      // If there are incomplete plans, show the most recent one
      if (relevantPlans.length > 0) {
        setCurrentPlan(relevantPlans[0]);
        setShowResumeDialog(true);
      } else {
        setCurrentPlan(null);
        setShowResumeDialog(false);
      }
    } catch (err) {
      console.error('Failed to fetch incomplete plans:', err);
      setError('Failed to fetch incomplete plans');
      setIncompletePlans([]);
    } finally {
      setIsLoading(false);
      setHasFetched(true);
    }
  }, [projectId, token]);

  // Fetch on mount (only once)
  useEffect(() => {
    if (!hasFetched) {
      fetchIncompletePlans();
    }
  }, [fetchIncompletePlans, hasFetched]);

  const handleResume = useCallback(async (plan: PlanData) => {
    if (!plan || !plan.db_id) return;
    
    try {
      // Update plan status to RUNNING in backend
      await proxyFetchPut(`/api/plan/${plan.db_id}`, {
        status: PLAN_STATUS.RUNNING,
      });
      
      // The chatStore and plan restoration is handled by the component using this hook
      // (ChatBox), which has access to the correct store instance.
      // We return the plan data so the component can restore it.
      
      setShowResumeDialog(false);
      setCurrentPlan(null);
    } catch (err) {
      console.error('Failed to resume plan:', err);
      setError('Failed to resume plan');
      throw err; // Re-throw so caller can handle
    }
  }, []);

  const handleDismiss = useCallback(() => {
    setShowResumeDialog(false);
    setCurrentPlan(null);
  }, []);

  return {
    incompletePlans,
    currentPlan,
    isLoading,
    error,
    showResumeDialog,
    setShowResumeDialog,
    handleResume,
    handleDismiss,
    refetch: fetchIncompletePlans,
  };
}

export default usePlanResume;
