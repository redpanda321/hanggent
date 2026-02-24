/**
 * usePlanHistory Hook
 * 
 * Fetches plan history with filtering and pagination.
 * Supports filtering by project and status.
 */

import { useState, useEffect, useCallback } from 'react';
import { proxyFetchGet } from '@/api/http';
import { PlanData } from '@/store/chatStore';
import { useAuthStore } from '@/store/authStore';

interface BackendPlan {
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

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
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

export type PlanStatusFilter = 'all' | 'completed' | 'failed' | 'incomplete';

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
function convertToPlanData(plan: BackendPlan): PlanData {
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
    db_id: plan.id,
    project_id: plan.project_id,
    task_id: plan.task_id,
    current_step_index: plan.current_step_index,
    created_at: plan.created_at,
    updated_at: plan.updated_at,
  };
}

export interface UsePlanHistoryOptions {
  projectId?: string | null;
  statusFilter?: PlanStatusFilter;
  page?: number;
  pageSize?: number;
  showAllProjects?: boolean;
}

export interface UsePlanHistoryResult {
  plans: PlanData[];
  isLoading: boolean;
  error: string | null;
  totalPlans: number;
  totalPages: number;
  currentPage: number;
  statusFilter: PlanStatusFilter;
  setStatusFilter: (filter: PlanStatusFilter) => void;
  setPage: (page: number) => void;
  refetch: () => Promise<void>;
}

export function usePlanHistory(options: UsePlanHistoryOptions = {}): UsePlanHistoryResult {
  const token = useAuthStore((s) => s.token);
  const {
    projectId,
    statusFilter: initialStatusFilter = 'all',
    page: initialPage = 1,
    pageSize = 10,
    showAllProjects = false,
  } = options;

  const [plans, setPlans] = useState<PlanData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalPlans, setTotalPlans] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [statusFilter, setStatusFilter] = useState<PlanStatusFilter>(initialStatusFilter);

  const fetchPlans = useCallback(async () => {
    if (!token) {
      setPlans([]);
      setTotalPlans(0);
      setTotalPages(0);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      let endpoint: string;
      const params = new URLSearchParams();
      params.set('page', currentPage.toString());
      params.set('size', pageSize.toString());
      
      if (statusFilter !== 'all') {
        params.set('status_filter', statusFilter);
      }

      if (showAllProjects || !projectId) {
        // Fetch all plans across projects
        endpoint = `/api/plan/all?${params.toString()}`;
      } else {
        // Fetch plans for specific project
        endpoint = `/api/plan/project/${projectId}?${params.toString()}`;
      }

      const response: PaginatedResponse<BackendPlan> = await proxyFetchGet(endpoint);
      
      const convertedPlans = (response?.items ?? []).map(convertToPlanData);
      setPlans(convertedPlans);
      setTotalPlans(response?.total ?? 0);
      setTotalPages(response?.pages ?? 0);
    } catch (err) {
      console.error('Failed to fetch plan history:', err);
      setError('Failed to fetch plan history');
      setPlans([]);
    } finally {
      setIsLoading(false);
    }
  }, [projectId, statusFilter, currentPage, pageSize, showAllProjects, token]);

  // Fetch on mount and when dependencies change
  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  // Reset page when filter changes
  const handleSetStatusFilter = useCallback((filter: PlanStatusFilter) => {
    setStatusFilter(filter);
    setCurrentPage(1);
  }, []);

  const handleSetPage = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  return {
    plans,
    isLoading,
    error,
    totalPlans,
    totalPages,
    currentPage,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    setPage: handleSetPage,
    refetch: fetchPlans,
  };
}

export default usePlanHistory;
