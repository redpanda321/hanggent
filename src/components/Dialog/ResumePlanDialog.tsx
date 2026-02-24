import { useCallback, useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Play, X, ListTodo } from "lucide-react";
import { PlanData } from "@/store/chatStore";

const AUTO_RESUME_STORAGE_KEY = "hanggent_plan_auto_resume";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: PlanData | null;
  onResume: (plan: PlanData) => void;
  onDismiss: () => void;
}

export function ResumePlanDialog({ 
  open, 
  onOpenChange, 
  plan, 
  onResume, 
  onDismiss 
}: Props) {
  const { t } = useTranslation();
  
  // Auto-resume preference state
  const [autoResumeEnabled, setAutoResumeEnabled] = useState(() => {
    try {
      return localStorage.getItem(AUTO_RESUME_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  // Handle auto-resume preference change
  const handleAutoResumeChange = useCallback((checked: boolean) => {
    setAutoResumeEnabled(checked);
    try {
      localStorage.setItem(AUTO_RESUME_STORAGE_KEY, String(checked));
    } catch (e) {
      console.warn("Failed to save auto-resume preference:", e);
    }
  }, []);

  // Auto-resume if enabled and dialog opens with a plan
  useEffect(() => {
    if (open && plan && autoResumeEnabled) {
      // Small delay to let the user see what's happening
      const timer = setTimeout(() => {
        onResume(plan);
        onOpenChange(false);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [open, plan, autoResumeEnabled, onResume, onOpenChange]);
  
  const handleResume = useCallback(() => {
    if (plan) {
      onResume(plan);
    }
    onOpenChange(false);
  }, [plan, onResume, onOpenChange]);

  const handleDismiss = useCallback(() => {
    onDismiss();
    onOpenChange(false);
  }, [onDismiss, onOpenChange]);

  if (!plan) return null;

  // Find the first incomplete step index
  const resumeStepIndex = plan.steps.findIndex(
    step => step.status === 'not_started' || step.status === 'in_progress'
  );
  const resumeStep = resumeStepIndex >= 0 ? plan.steps[resumeStepIndex] : null;

  // Calculate progress percentage
  const progressPercent = plan.total_steps > 0 
    ? Math.round((plan.completed_steps / plan.total_steps) * 100) 
    : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 !bg-popup-surface gap-0 !rounded-xl border border-zinc-300 shadow-sm">
        <DialogHeader className="!bg-popup-surface !rounded-t-xl p-md justify-start">
          <div className="flex items-center gap-2">
            <ListTodo className="w-5 h-5 text-blue-500" />
            <DialogTitle className="m-0">
              {t("plan.resume-interrupted-plan", "Resume Interrupted Plan?")}
            </DialogTitle>
          </div>
        </DialogHeader>
        
        <div className="flex flex-col gap-md bg-popup-bg p-md">
          {/* Plan info */}
          <div className="flex flex-col gap-2">
            <p className="text-sm text-text-secondary">
              {t("plan.found-incomplete-plan", "An incomplete plan was found:")}
            </p>
            <div className="p-3 bg-surface-secondary rounded-lg border border-border-default">
              <h4 className="font-medium text-text-primary mb-2">{plan.title}</h4>
              
              {/* Progress bar */}
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <span className="text-xs text-text-secondary tabular-nums">
                  {plan.completed_steps}/{plan.total_steps} steps
                </span>
              </div>
              
              {/* Resume point indicator */}
              {resumeStep && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-text-secondary">
                    {t("plan.will-resume-from", "Will resume from:")}
                  </span>
                  <span className="font-medium text-blue-600 dark:text-blue-400">
                    Step {resumeStepIndex + 1}: {resumeStep.title}
                  </span>
                </div>
              )}
            </div>
          </div>
          
          {/* Description */}
          <p className="text-sm text-text-secondary">
            {t(
              "plan.resume-description", 
              "Would you like to resume this plan from where it left off, or dismiss it and start fresh?"
            )}
          </p>

          {/* Auto-resume preference */}
          <div className="flex items-center gap-2 pt-2 border-t border-border-default">
            <Switch 
              id="auto-resume-switch"
              checked={autoResumeEnabled}
              onCheckedChange={handleAutoResumeChange}
            />
            <Label 
              htmlFor="auto-resume-switch" 
              className="text-sm text-text-secondary cursor-pointer select-none"
            >
              {t("plan.auto-resume-preference", "Always resume automatically")}
            </Label>
          </div>
        </div>
        
        <DialogFooter className="bg-white dark:bg-gray-900 !rounded-b-xl p-md gap-2">
          <Button 
            variant="ghost" 
            size="md" 
            onClick={handleDismiss}
            className="gap-2"
          >
            <X className="w-4 h-4" />
            {t("plan.dismiss", "Dismiss")}
          </Button>
          <Button 
            size="md" 
            onClick={handleResume}
            className="gap-2 bg-blue-600 hover:bg-blue-700 text-white"
          >
            <Play className="w-4 h-4" />
            {t("plan.resume", "Resume Plan")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
