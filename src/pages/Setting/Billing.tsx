import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  CreditCard, 
  Crown, 
  Zap, 
  Sparkles, 
  ExternalLink, 
  Calendar,
  AlertCircle,
  CheckCircle2,
  Coins,
  Plus,
  DollarSign,
  Info,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { proxyFetchGet, proxyFetchPost } from '@/api/http';
import { toast } from 'sonner';

interface SubscriptionStatus {
  plan: string;
  status: string | null;
  period_end: string | null;
  cancel_at_period_end: boolean;
}

interface PlansResponse {
  plans: PlanInfo[];
  stripe_enabled: boolean;
  publishable_key: string | null;
}

interface PlanInfo {
  id: string;
  name: string;
  price_monthly: number;
  free_tokens: number;
  default_spending_limit: number;
  minimum_topup: number;
  allowed_models: string[];
  support_level: string;
  features: string[];
  has_trial: boolean;
  trial_days: number;
}

interface CreditBalance {
  credits: number;
  plan: string;
  minimum_topup: number;
}

interface UsageStats {
  billing_period: string;
  plan: string;
  free_tokens_allowance: number;
  free_tokens_used: number;
  free_tokens_remaining: number;
  paid_tokens_used: number;
  total_tokens_used: number;
  total_spending: number;
  spending_limit: number;
  spending_remaining: number;
  spending_percentage: number;
  alert_threshold_reached: boolean;
  limit_reached: boolean;
  model_breakdown: Record<string, unknown>;
}

const TOP_UP_AMOUNTS = [1, 2, 5, 10]; // Preset top-up amounts in dollars

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: <Sparkles className="h-5 w-5" />,
  plus: <Zap className="h-5 w-5" />,
  pro: <Crown className="h-5 w-5" />,
};

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  plus: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  pro: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
};

export default function Billing() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const handledStripeReturnRef = useRef(false);
  
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [currentPlanInfo, setCurrentPlanInfo] = useState<PlanInfo | null>(null);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(false);
  const [creditBalance, setCreditBalance] = useState<CreditBalance | null>(null);
  const [topUpLoading, setTopUpLoading] = useState<number | null>(null);
  const [selectedAmount, setSelectedAmount] = useState<number | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);

  useEffect(() => {
    loadBillingData();
  }, []);

  useEffect(() => {
    // Handle Stripe redirect back into the SPA.
    // With HashRouter, react-router exposes the hash query string as location.search.
    if (handledStripeReturnRef.current) return;
    if (!location.search) return;

    const params = new URLSearchParams(location.search);
    const payment = params.get('payment');
    const topup = params.get('topup');
    const sessionId = params.get('session_id');

    const isPaymentSuccess = payment === 'success';
    const isTopupSuccess = topup === 'success';

    if (!isPaymentSuccess && !isTopupSuccess) return;

    handledStripeReturnRef.current = true;

    if (isPaymentSuccess) {
      toast.success(
        t(
          'billing.paymentSuccess',
          'Payment successful. Updating your subscription…'
        )
      );
    }
    if (isTopupSuccess) {
      toast.success(
        t('billing.topupSuccess', 'Top-up successful. Updating your balance…')
      );
    }

    // Verify the checkout session server-side to ensure credits are granted
    // even if the Stripe webhook hasn't arrived yet. Then refresh billing data.
    const verifyAndRefresh = async () => {
      let verifyStatus: 'complete' | 'pending' | 'failed' = 'complete';

      if (sessionId) {
        for (let attempt = 0; attempt < 3; attempt += 1) {
          try {
            const response = await proxyFetchPost('/payment/verify-session', {
              session_id: sessionId,
            });
            verifyStatus = response?.status === 'pending' ? 'pending' : 'complete';
            if (verifyStatus === 'complete') {
              break;
            }
          } catch (e) {
            console.warn('verify-session failed, will rely on webhook:', e);
            if (attempt === 2) {
              verifyStatus = 'failed';
              break;
            }
          }

          await new Promise((resolve) => setTimeout(resolve, 1200));
        }
      }

      await loadBillingData();

      if (verifyStatus !== 'complete') {
        toast.info(
          t(
            'billing.topupProcessing',
            'Payment is being finalized. Your balance will update shortly.'
          )
        );
      }
    };
    void verifyAndRefresh();

    // Clean up URL so success toasts don’t reappear on reload.
    params.delete('payment');
    params.delete('topup');
    params.delete('session_id');

    const nextSearch = params.toString();
    navigate(
      {
        pathname: location.pathname,
        search: nextSearch ? `?${nextSearch}` : '',
      },
      {
        replace: true,
        state: sessionId ? { stripe_session_id: sessionId } : undefined,
      }
    );
  }, [location.pathname, location.search, navigate, t]);

  const loadBillingData = async () => {
    try {
      // Load plans first to get plan info
      const plansResponse = await proxyFetchGet('/payment/plans') as PlansResponse;
      setStripeEnabled(plansResponse?.stripe_enabled ?? false);
      
      // Load subscription status
      const subscriptionResponse = await proxyFetchGet('/payment/subscription') as SubscriptionStatus;
      setSubscription(subscriptionResponse);
      
      // Find current plan info
      const planInfo = (plansResponse?.plans || []).find((p: PlanInfo) => p.id === subscriptionResponse?.plan);
      setCurrentPlanInfo(planInfo || null);
      
      // Load credit balance
      try {
        const balanceResponse = await proxyFetchGet('/usage/balance') as CreditBalance;
        setCreditBalance(balanceResponse);
      } catch (error) {
        console.error('Failed to load credit balance:', error);
      }
      
      // Load usage stats (for spending alert)
      try {
        const statsResponse = await proxyFetchGet('/usage/stats') as UsageStats;
        setUsageStats(statsResponse);
      } catch (error: any) {
        console.error('Failed to load usage stats:', error);
        // Show a non-blocking warning — billing page still works without stats
        if (error?.message?.includes('503') || error?.message?.includes('unavailable')) {
          toast.warning(t('billing.statsUnavailable', 'Usage statistics are temporarily unavailable. The billing system may still be initializing.'));
        }
      }
    } catch (error) {
      console.error('Failed to load billing data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleManageBilling = async () => {
    setPortalLoading(true);
    try {
      const response = await proxyFetchPost('/payment/portal', {
        return_url: `${window.location.origin}/#/history?tab=settings&settingsTab=billing`,
      }) as { portal_url: string };
      window.open(response.portal_url, '_blank');
    } catch (error: any) {
      toast.error(error.message || 'Failed to open billing portal');
    } finally {
      setPortalLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    if (!confirm(t('billing.confirmCancel', 'Are you sure you want to cancel your subscription? You will retain access until the end of your billing period.'))) {
      return;
    }
    
    setCancelLoading(true);
    try {
      await proxyFetchPost('/payment/cancel', {});
      toast.success(t('billing.cancelSuccess', 'Subscription will be canceled at the end of billing period'));
      loadBillingData();
    } catch (error: any) {
      toast.error(error.message || 'Failed to cancel subscription');
    } finally {
      setCancelLoading(false);
    }
  };

  const handleResumeSubscription = async () => {
    setResumeLoading(true);
    try {
      await proxyFetchPost('/payment/resume', {});
      toast.success(t('billing.resumeSuccess', 'Subscription resumed successfully'));
      loadBillingData();
    } catch (error: any) {
      toast.error(error.message || 'Failed to resume subscription');
    } finally {
      setResumeLoading(false);
    }
  };

  const handleTopUp = async (amount: number) => {
    if (!stripeEnabled) {
      toast.error(t('billing.stripeNotEnabled', 'Payment system is not configured'));
      return;
    }
    setTopUpLoading(amount);
    try {
      const response = await proxyFetchPost('/payment/topup', {
        amount: amount,
        success_url: window.location.href,
        cancel_url: window.location.href,
      }) as { checkout_url: string };
      window.location.href = response.checkout_url;
    } catch (error: any) {
      const message = error?.message || '';
      if (message.includes('503') || message.includes('misconfigured')) {
        toast.error(t('billing.paymentMisconfigured', 'Payment system is not available. Please try again later or contact support.'));
      } else {
        toast.error(message || 'Failed to create top-up checkout');
      }
    } finally {
      setTopUpLoading(null);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, { 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
  };

  const getStatusBadge = () => {
    if (!subscription) return null;
    
    if (subscription.cancel_at_period_end) {
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <AlertCircle className="h-3 w-3" />
          {t('billing.canceling', 'Canceling')}
        </Badge>
      );
    }
    
    if (subscription.status === 'active' || subscription.status === 'trialing') {
      return (
        <Badge variant="default" className="flex items-center gap-1 bg-green-600">
          <CheckCircle2 className="h-3 w-3" />
          {subscription.status === 'trialing' ? t('billing.trial', 'Trial') : t('billing.active', 'Active')}
        </Badge>
      );
    }
    
    if (subscription.status === 'past_due') {
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <AlertCircle className="h-3 w-3" />
          {t('billing.pastDue', 'Past Due')}
        </Badge>
      );
    }
    
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">
          {t('billing.title', 'Billing & Subscription')}
        </h2>
        <p className="text-muted-foreground">
          {t('billing.description', 'Manage your subscription and billing details')}
        </p>
      </div>

      {/* Current Plan Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full ${PLAN_COLORS[subscription?.plan || 'free']}`}>
                {PLAN_ICONS[subscription?.plan || 'free']}
              </div>
              <div>
                <CardTitle className="text-xl">
                  {currentPlanInfo?.name || 'Free'} {t('billing.plan', 'Plan')}
                </CardTitle>
                <CardDescription>
                  {currentPlanInfo && (
                    currentPlanInfo.price_monthly === 0 
                      ? t('billing.freePlan', 'No cost - perfect for getting started')
                      : `$${currentPlanInfo.price_monthly.toFixed(2)}/${t('billing.month', 'month')}`
                  )}
                </CardDescription>
              </div>
            </div>
            {getStatusBadge()}
          </div>
        </CardHeader>
        <CardContent>
          {/* Plan Features */}
          {currentPlanInfo && (
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-2xl font-bold">{currentPlanInfo.free_tokens.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">
                  {t('billing.freeTokens', 'Free tokens / month')}
                </div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-2xl font-bold">${currentPlanInfo.default_spending_limit.toFixed(0)}</div>
                <div className="text-sm text-muted-foreground">
                  {t('billing.spendingLimit', 'Spending limit')}
                </div>
              </div>
            </div>
          )}

          {/* Billing Period */}
          {subscription?.period_end && subscription.plan !== 'free' && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
              <Calendar className="h-4 w-4" />
              {subscription.cancel_at_period_end ? (
                <span>
                  {t('billing.accessUntil', 'Access until')}: {formatDate(subscription.period_end)}
                </span>
              ) : (
                <span>
                  {t('billing.renewsOn', 'Renews on')}: {formatDate(subscription.period_end)}
                </span>
              )}
            </div>
          )}

          <Separator className="my-4" />

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            {subscription?.plan === 'free' ? (
              <Button onClick={() => navigate('/history?tab=settings&settingsTab=pricing')}>
                <Zap className="h-4 w-4 mr-2" />
                {t('billing.upgradePlan', 'Upgrade Plan')}
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => navigate('/history?tab=settings&settingsTab=pricing')}>
                  {t('billing.changePlan', 'Change Plan')}
                </Button>
                
                {stripeEnabled && (
                  <Button 
                    variant="outline" 
                    onClick={handleManageBilling}
                    disabled={portalLoading}
                  >
                    <CreditCard className="h-4 w-4 mr-2" />
                    {portalLoading ? t('common.loading', 'Loading...') : t('billing.manageBilling', 'Manage Billing')}
                    <ExternalLink className="h-3 w-3 ml-2" />
                  </Button>
                )}

                {subscription && subscription.cancel_at_period_end ? (
                  <Button 
                    variant="primary"
                    onClick={handleResumeSubscription}
                    disabled={resumeLoading}
                  >
                    {resumeLoading ? t('common.loading', 'Loading...') : t('billing.resumeSubscription', 'Resume Subscription')}
                  </Button>
                ) : (
                  <Button 
                    variant="ghost" 
                    className="text-destructive hover:text-destructive"
                    onClick={handleCancelSubscription}
                    disabled={cancelLoading}
                  >
                    {cancelLoading ? t('common.loading', 'Loading...') : t('billing.cancelSubscription', 'Cancel Subscription')}
                  </Button>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Spending Alert Banner */}
      {usageStats && usageStats.alert_threshold_reached && !usageStats.limit_reached && (
        <Card className="border-amber-300 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-950/20">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 shrink-0">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-amber-800 dark:text-amber-200">
                  {t('billing.spendingAlertTitle', 'Approaching Spending Limit')}
                </h4>
                <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                  {t('billing.spendingAlertDescription', 
                    'You\'ve used {{percentage}}% of your ${{limit}} spending limit (${{spent}} spent). Consider increasing your limit to avoid service interruption.',
                    { 
                      percentage: usageStats.spending_percentage.toFixed(0),
                      limit: usageStats.spending_limit.toFixed(0),
                      spent: usageStats.total_spending.toFixed(2),
                    }
                  )}
                </p>
                <div className="mt-3 w-full bg-amber-200 dark:bg-amber-800 rounded-full h-2.5">
                  <div
                    className="bg-amber-600 dark:bg-amber-400 h-2.5 rounded-full transition-all"
                    style={{ width: `${Math.min(usageStats.spending_percentage, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Spending Limit Reached Banner */}
      {usageStats && usageStats.limit_reached && (
        <Card className="border-red-300 dark:border-red-700 bg-red-50/50 dark:bg-red-950/20">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 shrink-0">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-red-800 dark:text-red-200">
                  {t('billing.limitReachedTitle', 'Spending Limit Reached')}
                </h4>
                <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                  {t('billing.limitReachedDescription',
                    'You\'ve reached your ${{limit}} monthly spending limit (${{spent}} spent). Increase your limit or top up credits to continue using AI models.',
                    {
                      limit: usageStats.spending_limit.toFixed(0),
                      spent: usageStats.total_spending.toFixed(2),
                    }
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Credit Balance & Top-up Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                <Coins className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-xl">
                  {t('billing.creditBalance', 'Credit Balance')}
                </CardTitle>
                <CardDescription>
                  {t('billing.creditDescription', 'Pay-per-use credits for AI model usage')}
                </CardDescription>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Current Balance */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 border border-green-200 dark:border-green-800 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-1">
              <DollarSign className="h-5 w-5 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-700 dark:text-green-300">
                {t('billing.availableCredits', 'Available credits')}
              </span>
            </div>
            <div className="text-4xl font-bold text-green-600 dark:text-green-400">
              ${creditBalance?.credits?.toFixed(2) || '0.00'}
            </div>
          </div>

          <Separator className="my-4" />

          {/* Add Credits Section */}
          <div className="space-y-4">
            <h4 className="text-lg font-semibold flex items-center gap-2">
              <Plus className="h-4 w-4" />
              {t('billing.addCredits', 'Add Credits')}
            </h4>

            <div className="flex items-start gap-2 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 p-3">
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
              <p className="text-sm text-blue-700 dark:text-blue-300">
                {t('billing.topUpDescription', 'Credits never expire and can be used anytime after your free tokens are exhausted.')}
              </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {TOP_UP_AMOUNTS.map((amount) => (
                <button
                  key={amount}
                  onClick={() => setSelectedAmount(amount)}
                  disabled={topUpLoading !== null}
                  className={`relative flex flex-col items-center justify-center rounded-xl border-2 p-4 transition-all hover:shadow-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    selectedAmount === amount
                      ? 'border-primary bg-primary/5 shadow-md ring-2 ring-primary/20'
                      : 'border-border hover:border-primary/50 bg-card'
                  }`}
                >
                  {amount === 5 && (
                    <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold text-primary-foreground">
                      {t('billing.popular', 'Popular')}
                    </span>
                  )}
                  <DollarSign className={`h-5 w-5 mb-1 ${selectedAmount === amount ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className="text-2xl font-bold">{amount}</span>
                  <span className="text-xs text-muted-foreground mt-1">USD</span>
                </button>
              ))}
            </div>

            {/* Purchase Button */}
            <Button
              onClick={() => selectedAmount && handleTopUp(selectedAmount)}
              disabled={!selectedAmount || topUpLoading !== null || !stripeEnabled}
              className="w-full h-11 text-base"
              size="lg"
            >
              {topUpLoading !== null ? (
                <div className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
                  {t('billing.processing', 'Processing...')}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <CreditCard className="h-4 w-4" />
                  {selectedAmount
                    ? `${t('billing.payWithStripe', 'Pay')} $${selectedAmount} ${t('billing.withStripe', 'with Stripe')}`
                    : t('billing.selectAmount', 'Select an amount')
                  }
                </div>
              )}
            </Button>

            {!stripeEnabled && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-3">
                <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
                <p className="text-sm text-amber-700 dark:text-amber-300">
                  {t('billing.stripeNotEnabled', 'Payment system is not configured.')}
                  {' '}
                  {t('billing.stripeSetupHint', 'Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY in your GitHub repository secrets (Settings → Secrets and variables → Actions) to enable Stripe payments.')}
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Available Models Card */}
      {currentPlanInfo && (
        <Card>
          <CardHeader>
            <CardTitle>{t('billing.availableModels', 'Available Models')}</CardTitle>
            <CardDescription>
              {t('billing.modelsDescription', 'AI models included in your current plan')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {(currentPlanInfo.allowed_models || []).map((model) => (
                <Badge key={model} variant="secondary">
                  {model}
                </Badge>
              ))}
            </div>
            {subscription?.plan !== 'pro' && (
              <p className="text-sm text-muted-foreground mt-4">
                {t('billing.upgradeForMore', 'Upgrade to access more powerful models')}
                <Button 
                  variant="ghost" 
                  className="p-0 h-auto ml-1"
                  onClick={() => navigate('/history?tab=settings&settingsTab=pricing')}
                >
                  {t('billing.viewPlans', 'View plans')}
                </Button>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Payment History Link */}
      {stripeEnabled && subscription?.plan !== 'free' && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium">{t('billing.paymentHistory', 'Payment History')}</h4>
                <p className="text-sm text-muted-foreground">
                  {t('billing.viewInvoices', 'View invoices and payment history in Stripe')}
                </p>
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleManageBilling}
                disabled={portalLoading}
              >
                {t('billing.viewHistory', 'View History')}
                <ExternalLink className="h-3 w-3 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
