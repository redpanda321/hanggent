import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { loadStripe } from '@stripe/stripe-js';
import { Check, Zap, Crown, Sparkles, ArrowLeft, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { proxyFetchGet, proxyFetchPost } from '@/api/http';
import { useAuthStore } from '@/store/authStore';
import { toast } from 'sonner';

interface PlanInfo {
  id: string;
  name: string;
  price_monthly: number;
  price_yearly: number;
  free_tokens: number;
  default_spending_limit: number;
  allowed_models: string[];
  support_level: string;
  features: string[];
  has_trial: boolean;
  trial_days: number;
}

interface ModelPricing {
  model_id: string;
  input_price_per_1m: number;
  output_price_per_1m: number;
}

interface PlansResponse {
  plans: PlanInfo[];
  stripe_enabled: boolean;
  publishable_key: string | null;
}

interface SubscriptionStatus {
  plan: string;
  status: string | null;
  period_end: string | null;
  cancel_at_period_end: boolean;
}

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: <Sparkles className="h-6 w-6" />,
  plus: <Zap className="h-6 w-6" />,
  pro: <Crown className="h-6 w-6" />,
};

const PLAN_COLORS: Record<string, string> = {
  free: 'border-gray-200 dark:border-gray-700',
  plus: 'border-blue-500 ring-2 ring-blue-500/20',
  pro: 'border-purple-500 ring-2 ring-purple-500/20',
};

const MODEL_DISPLAY_NAMES: Record<string, string> = {
  'gpt-5': 'GPT-5 Chat',
  'gpt-4o-mini': 'GPT-4o Mini',
  'gpt-4o': 'GPT-4o',
  'gpt-4.5-preview': 'GPT-4.5 Preview',
  'gpt-4.1': 'GPT-4.1',
  'gpt-4.1-mini': 'GPT-4.1 Mini',
  'o1': 'o1',
  'o1-mini': 'o1 Mini',
  'o3-mini': 'o3 Mini',
  'claude-opus-4-20250514': 'Claude Opus 4',
  'claude-sonnet-4-20250514': 'Claude Sonnet 4',
  'claude-4-5-sonnet-20250514': 'Claude 4.5 Sonnet',
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
  'claude-3-haiku-20240307': 'Claude 3 Haiku',
  'gemini-2.5-pro': 'Gemini 2.5 Pro',
  'gemini-2.5-flash': 'Gemini 2.5 Flash',
  'gemini-2.0-flash': 'Gemini 2.0 Flash',
  'deepseek-chat': 'DeepSeek Chat',
  'deepseek-reasoner': 'DeepSeek Reasoner',
  'deepseek-v3.1': 'DeepSeek-V3.1',
  'kimi-k2': 'Kimi K2 (Open)',
  'grok-4-fast': 'Grok 4 Fast',
  'MiniMax-Text-01': 'MiniMax Text 01',
  'MiniMax-M1': 'MiniMax M1',
  'MiniMax-M2.5': 'MiniMax M2.5',
  'moonshot-v1-128k': 'Moonshot V1 128K',
  'kimi-k2.5': 'Kimi K2.5',
  'z1-preview': 'Z1 Preview',
  'qwen-plus': 'Qwen Plus',
  'qwen-max': 'Qwen Max',
  'qwen-turbo': 'Qwen Turbo',
  'glm-5': 'GLM 5',
  'deepseek-v3.2': 'DeepSeek V3.2',
  'gemini-3-flash': 'Gemini 3 Flash',
  'claude-sonnet-4.5': 'Claude Sonnet 4.5',
  'claude-opus-4.6': 'Claude Opus 4.6',
  'grok-4.1-fast': 'Grok 4.1 Fast',
  'gpt-5-nano': 'GPT-5 Nano',
  'gpt-5.2': 'GPT-5.2',
};

// Format token numbers for display (e.g., 100000 -> "100K", 1000000 -> "1M")
const formatTokens = (tokens: number): string => {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(tokens % 1000000 === 0 ? 0 : 1)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(tokens % 1000 === 0 ? 0 : 1)}K`;
  }
  return tokens.toString();
};

export default function Pricing() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token } = useAuthStore();
  const isAuthenticated = !!token;
  
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [modelPricing, setModelPricing] = useState<ModelPricing[]>([]);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [publishableKey, setPublishableKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [currentSubscription, setCurrentSubscription] = useState<SubscriptionStatus | null>(null);

  useEffect(() => {
    loadPlans();
    loadModelPricing();
    if (isAuthenticated) {
      loadSubscriptionStatus();
    }
  }, [isAuthenticated]);

  const loadPlans = async () => {
    try {
      const response = await proxyFetchGet('/payment/plans') as PlansResponse;
      setPlans(response.plans || []);
      setStripeEnabled(response.stripe_enabled ?? false);
      setPublishableKey(response.publishable_key ?? '');
    } catch (error) {
      console.error('Failed to load plans:', error);
      toast.error('Failed to load pricing plans');
    } finally {
      setLoading(false);
    }
  };

  const loadModelPricing = async () => {
    try {
      const response = await proxyFetchGet('/usage/model-pricing') as { models: ModelPricing[] };
      setModelPricing(response.models || []);
    } catch (error) {
      console.error('Failed to load model pricing:', error);
    }
  };

  const loadSubscriptionStatus = async () => {
    try {
      const response = await proxyFetchGet('/payment/subscription') as SubscriptionStatus;
      setCurrentSubscription(response);
    } catch (error) {
      console.error('Failed to load subscription status:', error);
    }
  };

  const handleCheckout = async (planId: string) => {
    if (!isAuthenticated) {
      navigate('/login', { state: { returnTo: '/pricing' } });
      return;
    }

    if (!stripeEnabled || !publishableKey) {
      toast.error('Payment system is not available');
      return;
    }

    if (isCurrentPlan(planId)) {
      toast.error(
        t('pricing.alreadySubscribed', 'You are already subscribed to this plan.')
      );
      return;
    }

    if (isPlusCheckoutBlocked(planId)) {
      toast.error(
        t(
          'pricing.cancelProFirst',
          'Cancel Pro first. You can switch to Plus after cancellation is scheduled.'
        )
      );
      return;
    }

    setCheckoutLoading(planId);

    try {
      const stripe = await loadStripe(publishableKey);
      if (!stripe) {
        throw new Error('Failed to load Stripe');
      }

      const baseUrl = window.location.origin;
      const response = await proxyFetchPost(
        '/payment/checkout',
        {
          plan_id: planId,
          billing_cycle: 'monthly',
          // Route back to the existing Settings tab inside History.
          // Keep params in the hash fragment so the SPA can read them.
          success_url: `${baseUrl}/#/history?tab=settings&payment=success`,
          cancel_url: `${baseUrl}/#/pricing`,
        }
      ) as { checkout_url: string; session_id: string };

      // Redirect to Stripe Checkout
      window.location.href = response.checkout_url;
    } catch (error: any) {
      console.error('Checkout error:', error);
      toast.error(error.message || 'Failed to start checkout');
    } finally {
      setCheckoutLoading(null);
    }
  };

  const getPrice = (plan: PlanInfo) => {
    return plan.price_monthly;
  };

  const getPriceLabel = (plan: PlanInfo) => {
    if (plan.price_monthly === 0) return t('pricing.free', 'Free');
    const price = getPrice(plan);
    const period = t('pricing.month', '/month');
    return `$${price.toFixed(2)}${period}`;
  };

  const isCurrentPlan = (planId: string) => {
    return currentSubscription?.plan === planId;
  };

  const isPlusCheckoutBlocked = (planId: string) => {
    return (
      planId === 'plus' &&
      currentSubscription?.plan === 'pro' &&
      !currentSubscription?.cancel_at_period_end
    );
  };

  const canUpgrade = (planId: string) => {
    if (!currentSubscription) return true;
    const planOrder = ['free', 'plus', 'pro'];
    const currentIndex = planOrder.indexOf(currentSubscription.plan);
    const targetIndex = planOrder.indexOf(planId);
    return targetIndex > currentIndex;
  };

  const getButtonText = (plan: PlanInfo) => {
    if (isCurrentPlan(plan.id)) {
      return t('pricing.currentPlan', 'Current Plan');
    }
    if (isPlusCheckoutBlocked(plan.id)) {
      return t('pricing.cancelProFirst', 'Cancel Pro first');
    }
    if (plan.id === 'free') {
      return t('pricing.getStarted', 'Get Started');
    }
    if (plan.has_trial && plan.trial_days > 0) {
      return t('pricing.startTrial', `Start ${plan.trial_days}-Day Free Trial`);
    }
    return canUpgrade(plan.id) 
      ? t('pricing.upgrade', 'Upgrade') 
      : t('pricing.downgrade', 'Downgrade');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <Button
            variant="ghost"
            className="mb-6"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('common.back', 'Back')}
          </Button>
          
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            {t('pricing.title', 'Choose Your Plan')}
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            {t('pricing.subtitle', 'Start free and scale as you grow. All plans include core features.')}
          </p>
        </div>

        {/* Plans Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan) => (
            <Card
              key={plan.id}
              className={`relative flex flex-col ${PLAN_COLORS[plan.id]} ${
                plan.id === 'plus' ? 'scale-105 shadow-xl' : ''
              }`}
            >
              {plan.id === 'plus' && (
                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-500">
                  {t('pricing.popular', 'Most Popular')}
                </Badge>
              )}
              
              <CardHeader className="text-center pb-4">
                <div className={`mx-auto mb-4 p-3 rounded-full ${
                  plan.id === 'free' ? 'bg-gray-100 dark:bg-gray-800' :
                  plan.id === 'plus' ? 'bg-blue-100 dark:bg-blue-900' :
                  'bg-purple-100 dark:bg-purple-900'
                }`}>
                  {PLAN_ICONS[plan.id]}
                </div>
                <CardTitle className="text-2xl">{plan.name}</CardTitle>
                <CardDescription>
                  <span className="text-3xl font-bold text-foreground">
                    {getPriceLabel(plan)}
                  </span>
                </CardDescription>
                {plan.has_trial && plan.trial_days > 0 && (
                  <Badge variant="secondary" className="mt-2">
                    {t('pricing.trialBadge', `${plan.trial_days}-day free trial`)}
                  </Badge>
                )}
              </CardHeader>

              <CardContent className="flex-grow">
                <ul className="space-y-3">
                  {plan.features.map((feature, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <Check className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                      <span>{feature}</span>
                    </li>
                  ))}
                  <li className="flex items-start gap-2">
                    <Check className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                    <span>
                      {plan.support_level === 'email' && t('pricing.emailSupport', 'Email support')}
                      {plan.support_level === 'priority_email' && t('pricing.prioritySupport', 'Priority email support')}
                      {plan.support_level === 'high_priority' && t('pricing.highPrioritySupport', 'High-priority support')}
                    </span>
                  </li>
                  {plan.id !== 'free' && (
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      <span>
                        {t('pricing.payPerUse', `Pay-per-use after free tokens (up to $${plan.default_spending_limit} default limit)`)}
                      </span>
                    </li>
                  )}
                </ul>
              </CardContent>

              <CardFooter>
                <Button
                  className={`w-full ${
                    plan.id === 'plus' ? 'bg-blue-600 hover:bg-blue-700' :
                    plan.id === 'pro' ? 'bg-purple-600 hover:bg-purple-700' :
                    ''
                  }`}
                  variant={plan.id === 'free' ? 'outline' : 'primary'}
                  disabled={
                    isCurrentPlan(plan.id) ||
                    checkoutLoading !== null ||
                    isPlusCheckoutBlocked(plan.id)
                  }
                  onClick={() => {
                    if (plan.id === 'free') {
                      navigate('/signup');
                    } else {
                      handleCheckout(plan.id);
                    }
                  }}
                >
                  {checkoutLoading === plan.id ? (
                    <span className="flex items-center gap-2">
                      <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                      {t('pricing.processing', 'Processing...')}
                    </span>
                  ) : (
                    getButtonText(plan)
                  )}
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>

        {/* Features Comparison */}
        <div className="mt-16 text-center">
          <h2 className="text-2xl font-bold mb-4">
            {t('pricing.allPlansInclude', 'All Plans Include')}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto text-sm text-muted-foreground">
            <div className="flex items-center justify-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              {t('pricing.feature1', '9 Specialized Agents')}
            </div>
            <div className="flex items-center justify-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              {t('pricing.feature2', 'Browser Automation')}
            </div>
            <div className="flex items-center justify-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              {t('pricing.feature3', 'Local File Access')}
            </div>
            <div className="flex items-center justify-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              {t('pricing.feature4', 'MCP Support')}
            </div>
          </div>
        </div>

        {/* Model Pricing Table */}
        {modelPricing.length > 0 && (
          <div className="mt-16">
            <h2 className="text-2xl font-bold text-center mb-4">
              {t('pricing.modelPricing', 'Model Pricing')}
            </h2>
            <p className="text-center text-muted-foreground mb-8">
              {t('pricing.modelPricingDesc', 'Pay-per-use pricing after your free token allowance. Prices per 1M tokens.')}
            </p>
            <div className="max-w-4xl mx-auto overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('pricing.model', 'Model')}</TableHead>
                    <TableHead className="text-right">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger className="flex items-center gap-1 ml-auto">
                            {t('pricing.inputTokens', 'Input')}
                            <Info className="h-3 w-3" />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{t('pricing.inputTooltip', 'Cost per 1M input tokens (prompts, context)')}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableHead>
                    <TableHead className="text-right">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger className="flex items-center gap-1 ml-auto">
                            {t('pricing.outputTokens', 'Output')}
                            <Info className="h-3 w-3" />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{t('pricing.outputTooltip', 'Cost per 1M output tokens (responses)')}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {modelPricing.map((model) => (
                    <TableRow key={model.model_id}>
                      <TableCell className="font-medium">
                        {MODEL_DISPLAY_NAMES[model.model_id] || model.model_id}
                      </TableCell>
                      <TableCell className="text-right">
                        ${model.input_price_per_1m.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right">
                        ${model.output_price_per_1m.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {/* Chinese Model Value Ranking */}
        <div className="mt-16">
          <h2 className="text-2xl font-bold text-center mb-2">
            {t('pricing.chinaModelRanking', '\uD83C\uDDE8\uD83C\uDDF3 China Model Value Ranking')}
          </h2>
          <p className="text-center text-muted-foreground mb-6">
            {t('pricing.chinaModelRankingDesc', 'Best value Chinese LLMs ranked by cost-effectiveness. Prices per 1M tokens.')}
          </p>
          <div className="max-w-4xl mx-auto overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12 text-center">#</TableHead>
                  <TableHead>{t('pricing.model', 'Model')}</TableHead>
                  <TableHead className="text-right">{t('pricing.inputPrice', 'Input $/1M')}</TableHead>
                  <TableHead className="text-right">{t('pricing.outputPrice', 'Output $/1M')}</TableHead>
                  <TableHead className="text-center">{t('pricing.overallCost', 'Overall Cost')}</TableHead>
                  <TableHead className="text-center">{t('pricing.valueIndex', 'Value')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow className="bg-yellow-50 dark:bg-yellow-950/20">
                  <TableCell className="text-center font-bold">1</TableCell>
                  <TableCell className="font-medium">MiniMax M2.5 <span className="text-muted-foreground text-sm">(MiniMax)</span></TableCell>
                  <TableCell className="text-right">~$0.30</TableCell>
                  <TableCell className="text-right">~$1.20</TableCell>
                  <TableCell className="text-center">⭐ Lowest</TableCell>
                  <TableCell className="text-center text-xl">🥇</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-center font-bold">2</TableCell>
                  <TableCell className="font-medium">DeepSeek V3.2 <span className="text-muted-foreground text-sm">(DeepSeek)</span></TableCell>
                  <TableCell className="text-right">~$0.55</TableCell>
                  <TableCell className="text-right">~$1.70</TableCell>
                  <TableCell className="text-center">⭐ Best Value</TableCell>
                  <TableCell className="text-center text-xl">🥈</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-center font-bold">3</TableCell>
                  <TableCell className="font-medium">Kimi K2.5 <span className="text-muted-foreground text-sm">(Moonshot AI)</span></TableCell>
                  <TableCell className="text-right">~$0.60</TableCell>
                  <TableCell className="text-right">~$3.00</TableCell>
                  <TableCell className="text-center">Medium-High</TableCell>
                  <TableCell className="text-center text-xl">🥉</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-center font-bold">4</TableCell>
                  <TableCell className="font-medium">GLM 5 <span className="text-muted-foreground text-sm">(Zhipu AI)</span></TableCell>
                  <TableCell className="text-right">~$1.00</TableCell>
                  <TableCell className="text-right">~$3.20</TableCell>
                  <TableCell className="text-center">High</TableCell>
                  <TableCell className="text-center text-xl">❌</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Global Frontier Models */}
        <div className="mt-16">
          <h2 className="text-2xl font-bold text-center mb-2">
            {t('pricing.globalModels', '\uD83C\uDF0D Global Frontier Models')}
          </h2>
          <p className="text-center text-muted-foreground mb-6">
            {t('pricing.globalModelsDesc', 'Latest frontier models from leading AI labs. Prices per 1M tokens.')}
          </p>
          <div className="max-w-5xl mx-auto overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('pricing.model', 'Model')}</TableHead>
                  <TableHead>{t('pricing.company', 'Company')}</TableHead>
                  <TableHead className="text-right">{t('pricing.inputPrice', 'Input $/1M')}</TableHead>
                  <TableHead className="text-right">{t('pricing.outputPrice', 'Output $/1M')}</TableHead>
                  <TableHead>{t('pricing.highlights', 'Highlights')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="font-medium">GPT-5 Nano</TableCell>
                  <TableCell>OpenAI</TableCell>
                  <TableCell className="text-right">~$0.20</TableCell>
                  <TableCell className="text-right">~$0.80</TableCell>
                  <TableCell><Badge variant="secondary">Cheap & Light</Badge></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Gemini 2.5 Flash</TableCell>
                  <TableCell>Google</TableCell>
                  <TableCell className="text-right">~$0.30</TableCell>
                  <TableCell className="text-right">~$0.90</TableCell>
                  <TableCell><Badge variant="secondary">Ultra Low Price</Badge></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Gemini 3 Flash</TableCell>
                  <TableCell>Google</TableCell>
                  <TableCell className="text-right">~$0.35</TableCell>
                  <TableCell className="text-right">~$1.05</TableCell>
                  <TableCell><Badge variant="secondary">Fast + Cheap</Badge></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">GPT-5.2</TableCell>
                  <TableCell>OpenAI</TableCell>
                  <TableCell className="text-right">~$2.00</TableCell>
                  <TableCell className="text-right">~$8.00</TableCell>
                  <TableCell><Badge variant="secondary">Strong General</Badge></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Claude Sonnet 4.5</TableCell>
                  <TableCell>Anthropic</TableCell>
                  <TableCell className="text-right">~$3.00</TableCell>
                  <TableCell className="text-right">~$15.00</TableCell>
                  <TableCell><Badge variant="outline">Strong but Pricey</Badge></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Grok 4.1 Fast</TableCell>
                  <TableCell>xAI</TableCell>
                  <TableCell className="text-right">~$5.00</TableCell>
                  <TableCell className="text-right">~$15.00</TableCell>
                  <TableCell><Badge variant="secondary">High-Speed Chat</Badge></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Claude Opus 4.6</TableCell>
                  <TableCell>Anthropic</TableCell>
                  <TableCell className="text-right">~$15.00</TableCell>
                  <TableCell className="text-right">~$75.00</TableCell>
                  <TableCell><Badge variant="outline">Top-Tier Premium</Badge></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </div>

        {/* FAQ or Contact */}
        <div className="mt-16 text-center text-muted-foreground">
          <p>
            {t('pricing.questions', 'Have questions?')}{' '}
            <a href="mailto:support@hangent.com" className="text-primary underline">
              {t('pricing.contactUs', 'Contact us')}
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
