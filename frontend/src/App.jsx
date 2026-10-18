import { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { Bug, Activity, FileDown } from 'lucide-react';
import { api } from './api';
import LoginPage from './components/LoginPage';
import AnalyzePanel from './components/AnalyzePanel';
import KpiStrip from './components/KpiStrip';
import UserMenu from './components/UserMenu';
import ResultViewer from './components/ResultViewer';
import HistoryTable from './components/HistoryTable';
import ThemeToggle from './components/ThemeToggle';
import LanguageToggle from './components/LanguageToggle';
import { useI18n } from './i18n';
import { useToast } from './ToastContext';
import VideoResultPanel from './components/VideoResultPanel';

// Recharts is heavy: load the chart panels and the admin area on demand.
const StatsPanel = lazy(() => import('./components/StatsPanel'));
const MetricsPanel = lazy(() => import('./components/MetricsPanel'));
const AdminDashboard = lazy(() => import('./components/AdminDashboard'));

const PanelFallback = ({ height = 'h-48' }) => <div className={`skeleton ${height}`} aria-hidden="true" />;

export default function App() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [user, setUser] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [stats, setStats] = useState(null);
  const [historyKey, setHistoryKey] = useState(0);
  const [result, setResult] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [videoResult, setVideoResult] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [adminMode, setAdminMode] = useState(false);

  // Cursor-following spotlight on every .panel (CSS reads --mx / --my).
  useEffect(() => {
    const onMove = (event) => {
      const panel = event.target.closest?.('.panel');
      if (!panel) return;
      const rect = panel.getBoundingClientRect();
      panel.style.setProperty('--mx', `${event.clientX - rect.left}px`);
      panel.style.setProperty('--my', `${event.clientY - rect.top}px`);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('bugsight_token');
    const savedUser = localStorage.getItem('bugsight_user');
    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('bugsight_user');
      }
    }
  }, []);

  useEffect(() => {
    const onSessionExpired = () => {
      setUser(null);
      toast.error({ key: 'app.sessionExpired' });
    };
    window.addEventListener('bugsight:session-expired', onSessionExpired);
    return () => window.removeEventListener('bugsight:session-expired', onSessionExpired);
  }, [toast]);

  // Stats only: the history table fetches (and paginates) its own data and is
  // refetched through `historyKey`.
  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.stats());
    } catch {
      toast.error({ key: 'app.apiUnreachable' });
    }
  }, [toast]);

  const refreshData = useCallback(() => {
    refreshStats();
    setHistoryKey((key) => key + 1);
  }, [refreshStats]);

  useEffect(() => {
    if (user) {
      refreshData();
      api.metrics().then(setMetrics).catch(() => setMetrics(null));
    }
  }, [user, refreshData]);

  const handlePredict = async (file, confidence) => {
    setLoading(true);
    setResult(null);
    // Release the previous preview so repeated analyses don't leak blob URLs.
    setImageUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return URL.createObjectURL(file);
    });
    try {
      const res = await api.predict(file, confidence);
      setResult(res);
      refreshData();
    } catch (e) {
      toast.error(e.response?.data?.error || { key: 'app.predictionFailed' });
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleVideoReport = (res) => {
    setVideoResult(res);
    // Video analyses are now persisted server-side too (see /api/predict-video),
    // so pull the updated history/stats the same way image predictions do.
    refreshData();
  };

  const handleDownloadReport = async () => {
    setReportLoading(true);
    try {
      await api.report(videoResult, lang);
    } catch (e) {
      toast.error({ key: 'app.reportFailed' });
    } finally {
      setReportLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('bugsight_token');
    localStorage.removeItem('bugsight_refresh_token');
    localStorage.removeItem('bugsight_user');
    setUser(null);
    setResult(null);
    setStats(null);
    setHistoryKey(0);
    setVideoResult(null);
    setAdminMode(false);
  };

  if (!user) {
    return <LoginPage onLogin={setUser} />;
  }

  if (adminMode && user.role === 'admin') {
    return (
      <div className="min-h-screen bg-[#F4F7F7] dark:bg-[#0A0E14] p-6 md:p-10">
        <div className="max-w-7xl mx-auto">
          <Suspense fallback={<PanelFallback height="h-96" />}>
            <AdminDashboard currentUser={user} onBack={() => setAdminMode(false)} />
          </Suspense>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F4F7F7] dark:bg-[#0A0E14] relative transition-colors">
      <div className="aurora" aria-hidden="true">
        <span className="aurora__blob aurora__blob--a" />
        <span className="aurora__blob aurora__blob--b" />
        <span className="aurora__blob aurora__blob--c" />
      </div>

      <div className="bs-root bs-grid-bg relative z-[1] min-h-screen">
        <header className="bg-white/90 dark:bg-[#0D1219]/90 border-b border-[#DCE6E8] dark:border-[#1E2733] header-glow top-0 z-20 backdrop-blur-xl transition-colors">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="bs-reticle w-10 h-10 rounded-md bg-[#F4F7F7] dark:bg-[#111826] border border-[#DCE6E8] dark:border-[#243040] flex items-center justify-center overflow-hidden">
                <div className="bs-scan" />
                <Bug className="w-5 h-5 text-[#0D9488] dark:text-[#5EEAD4]" />
              </div>
              <div className="hidden items-center gap-2 min-[480px]:flex">
                <h1 className="bs-mono whitespace-nowrap text-base font-semibold text-[#0F1B24] dark:text-white tracking-wide uppercase">
                  <span className="brand-gradient">BugSight QA</span>
                </h1>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="bs-pulse-dot absolute inline-flex h-1.5 w-1.5 rounded-full bg-[#0D9488] dark:bg-[#5EEAD4]" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#0D9488] dark:bg-[#5EEAD4]" />
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-3">
              <button
                onClick={handleDownloadReport}
                disabled={reportLoading}
                className="btn-primary btn-primary--auto !rounded-lg !px-3.5 !py-2"
              >
                {reportLoading ? (
                  <span className="bs-mono">{t('app.generating')}</span>
                ) : (
                  <>
                    <FileDown className="w-4 h-4" /> <span className="hidden sm:inline">{t('app.reportPdf')}</span>
                  </>
                )}
              </button>
              <LanguageToggle />
              <ThemeToggle />
              <UserMenu user={user} onAdmin={() => setAdminMode(true)} onLogout={handleLogout} />
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <div className="page-head mb-6">
            <p className="eyebrow">{t('stats.title')}</p>
            <h2 className="mt-1 text-2xl font-bold text-[#0F1B24] dark:text-white sm:text-3xl">
              {t('app.hello', { name: user.name })}
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-[#5B6B74] dark:text-gray-400">{t('app.overviewSub')}</p>
          </div>

          <KpiStrip stats={stats} metrics={metrics} />

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <div className="lg:sticky lg:top-24">
                <AnalyzePanel onPredict={handlePredict} loading={loading} onVideoReport={handleVideoReport} />
              </div>
            </div>

            <div className="space-y-6 lg:col-span-8">
              {(result || loading || !videoResult) && (
                <ResultViewer result={result} imageUrl={imageUrl} loading={loading} />
              )}
              {videoResult && <VideoResultPanel result={videoResult} />}
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            <Suspense fallback={<PanelFallback height="h-64" />}>
              <StatsPanel stats={stats} />
              <MetricsPanel metrics={metrics} />
            </Suspense>
          </div>

          <div className="mt-6">
            <HistoryTable refreshKey={historyKey} onChanged={refreshStats} />
          </div>

          <footer className="mt-12 pt-6 border-t border-[#DCE6E8] dark:border-[#1A222D] text-center">
            <p className="bs-mono text-[11px] text-[#5B6B74] dark:text-gray-600 flex items-center justify-center gap-2 tracking-wide">
              <Activity className="w-3.5 h-3.5 text-[#0D9488]/70 dark:text-[#5EEAD4]/70" />
              BUGSIGHT QA <span className="text-gray-400 dark:text-gray-700">·</span> YOLOv8 + Flask + React
              <span className="text-gray-400 dark:text-gray-700">·</span> PFA Project BY ALA JAMLI 
            </p>
          </footer>
        </main>
      </div>
    </div>
  );
}