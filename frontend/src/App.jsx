import { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { Bug, Activity, LogOut, FileDown, ShieldCheck } from 'lucide-react';
import { api } from './api';
import LoginPage from './components/LoginPage';
import UploadPanel from './components/UploadPanel';
import VideoAnalysis from './components/VideoAnalysis';
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
      <div className="bs-root bs-grid-bg bs-glow min-h-screen">
        <header className="bg-white/90 dark:bg-[#0D1219]/90 border-b border-[#DCE6E8] dark:border-[#1E2733] sticky top-0 z-10 backdrop-blur transition-colors">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="bs-reticle w-11 h-11 rounded-md bg-[#F4F7F7] dark:bg-[#111826] border border-[#DCE6E8] dark:border-[#243040] flex items-center justify-center overflow-hidden">
                <div className="bs-scan" />
                <Bug className="w-5 h-5 text-[#0D9488] dark:text-[#5EEAD4]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="bs-mono text-base font-semibold text-[#0F1B24] dark:text-white tracking-wide uppercase">
                    BugSight <span className="text-[#0D9488] dark:text-[#5EEAD4]">QA</span>
                  </h1>
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="bs-pulse-dot absolute inline-flex h-1.5 w-1.5 rounded-full bg-[#0D9488] dark:bg-[#5EEAD4]" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#0D9488] dark:bg-[#5EEAD4]" />
                  </span>
                </div>
                <p className="bs-mono text-[11px] text-[#5B6B74] dark:text-gray-500 tracking-wide">
                  {t('app.welcome')}, <span className="text-[#0F1B24] dark:text-gray-400">{user.name}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => user.role === 'admin' && setAdminMode(true)}
                disabled={user.role !== 'admin'}
                title={user.role === 'admin' ? t('app.adminOpen') : t('app.adminOnly')}
                className="flex items-center gap-1.5 px-3.5 py-1.5 border border-[#DCE6E8] dark:border-[#243040] rounded-md text-sm font-semibold text-[#0D9488] dark:text-[#5EEAD4] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ShieldCheck className="w-4 h-4" /> {t('app.admin')}
              </button>
              <button
                onClick={handleDownloadReport}
                disabled={reportLoading}
                className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] dark:bg-[#5EEAD4] dark:hover:bg-[#7FF3E0] disabled:bg-gray-200 dark:disabled:bg-[#1E2733] disabled:text-gray-400 dark:disabled:text-gray-500 text-white dark:text-[#0A0E14] rounded-md text-sm font-semibold transition-colors"
              >
                {reportLoading ? (
                  <span className="bs-mono">{t('app.generating')}</span>
                ) : (
                  <>
                    <FileDown className="w-4 h-4" /> {t('app.reportPdf')}
                  </>
                )}
              </button>
              <span className="bs-mono text-xs text-[#5B6B74] dark:text-gray-500 hidden md:block border-l border-[#DCE6E8] dark:border-[#243040] pl-3">
                {user.email}
              </span>
              <LanguageToggle />
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-transparent hover:bg-[#F4F7F7] dark:hover:bg-[#161D28] border border-[#DCE6E8] dark:border-[#243040] text-[#5B6B74] dark:text-gray-400 hover:text-[#0F1B24] dark:hover:text-gray-200 rounded-md text-sm font-medium transition-colors"
              >
                <LogOut className="w-4 h-4" /> {t('app.logout')}
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-6 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="space-y-6">
              <UploadPanel onPredict={handlePredict} loading={loading} />
              <VideoAnalysis onVideoReport={handleVideoReport} hideResult />
              <Suspense fallback={<PanelFallback />}>
                <StatsPanel stats={stats} />
              </Suspense>
              <HistoryTable refreshKey={historyKey} onChanged={refreshStats} />
            </div>

            <div className="lg:col-span-2 space-y-6">
              {result ? <ResultViewer result={result} imageUrl={imageUrl} /> : !videoResult && <ResultViewer result={null} imageUrl={null} />}
              {videoResult && <VideoResultPanel result={videoResult} />}
            </div>
          </div>

          <div className="mt-6">
            <Suspense fallback={<PanelFallback height="h-56" />}>
              <MetricsPanel metrics={metrics} />
            </Suspense>
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