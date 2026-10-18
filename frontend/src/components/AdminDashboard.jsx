import { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, BarChart3, CheckCircle2, Database, RefreshCw,
  ShieldCheck, Trash2, Users, Video, Image as ImageIcon,
} from 'lucide-react';
import { api } from '../api';
import { useI18n } from '../i18n';
import LanguageToggle from './LanguageToggle';
import ThemeToggle from './ThemeToggle';

const formatBytes = (bytes = 0) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

function Status({ ok, label }) {
  return <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
    {ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}{label}
  </span>;
}

export default function AdminDashboard({ currentUser, onBack }) {
  const { t, tError, formatDateTime: dateLabel } = useI18n();
  const [overview, setOverview] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyUser, setBusyUser] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, allAnalyses] = await Promise.all([api.adminOverview(), api.adminAnalyses()]);
      setOverview(data);
      setAnalyses(allAnalyses.predictions || []);
    } catch (err) {
      setError(err.response?.data?.error || { key: 'admin.loadFailed' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const changeRole = async (user) => {
    const role = user.role === 'admin' ? 'tester' : 'admin';
    if (!window.confirm(t('admin.confirmRole', { name: user.name, role: t(`role.${role}`) }))) return;
    setBusyUser(user.id);
    try {
      await api.adminUpdateRole(user.id, role);
      await load();
    } catch (err) {
      setError(err.response?.data?.error || { key: 'admin.roleFailed' });
    } finally { setBusyUser(null); }
  };

  const deleteUser = async (user) => {
    if (!window.confirm(t('admin.confirmDelete', { name: user.name }))) return;
    setBusyUser(user.id);
    try {
      await api.adminDeleteUser(user.id);
      await load();
    } catch (err) {
      setError(err.response?.data?.error || { key: 'admin.deleteFailed' });
    } finally { setBusyUser(null); }
  };

  if (loading && !overview) return <div className="py-20 text-center text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-3" />{t('admin.loading')}</div>;
  if (!overview) return <div className="p-6 bg-red-50 text-red-700 rounded-lg">{tError(error) || t('admin.unavailable')}</div>;

  const { stats, users, system } = overview;
  const ratio = Math.min(100, (system.storage_usage_ratio || 0) * 100);
  const cardClass = 'bg-white/90 dark:bg-[#0D1219]/90 border border-[#DCE6E8] dark:border-[#243040] rounded-lg p-5';

  return <section className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="bs-mono text-[11px] tracking-[0.18em] text-teal-600 dark:text-teal-300 uppercase">{t('admin.eyebrow')}</p><h2 className="text-2xl font-semibold text-gray-900 dark:text-white">{t('admin.heading')}</h2><p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('admin.connectedAs', { name: currentUser.name })}</p></div>
      <div className="flex flex-wrap items-center gap-2"><LanguageToggle /><ThemeToggle /><button onClick={load} className="inline-flex items-center gap-2 px-3 py-2 border rounded-md text-sm dark:border-gray-700 dark:text-gray-200"><RefreshCw className="w-4 h-4" /> {t('admin.refresh')}</button><button onClick={onBack} className="px-3 py-2 rounded-md bg-teal-600 text-white text-sm">{t('admin.back')}</button></div>
    </div>
    {error && <div className="p-3 rounded-md bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 text-sm text-red-700 dark:text-red-300">{tError(error)}</div>}

    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {[[Users, t('admin.kpiUsers'), users.length, 'teal'], [BarChart3, t('admin.kpiAnalyses'), stats.total_analyses, 'blue'], [AlertTriangle, t('admin.kpiWithBugs'), stats.bug_detected, 'orange'], [CheckCircle2, t('admin.kpiBugRate'), `${(stats.bug_rate * 100).toFixed(1)}%`, 'emerald']].map(([Icon, label, value, color]) => <div className={cardClass} key={label}><Icon className={`w-5 h-5 text-${color}-500 mb-3`} /><p className="text-xs uppercase tracking-wide text-gray-500">{label}</p><p className="text-2xl font-semibold text-gray-900 dark:text-white mt-1">{value}</p></div>)}
    </div>

    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <div className={`${cardClass} xl:col-span-2`}><div className="flex items-center gap-2 mb-4"><Users className="w-5 h-5 text-teal-500" /><h3 className="font-semibold text-gray-900 dark:text-white">{t('admin.allUsers')}</h3></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase text-gray-500 border-b dark:border-gray-700"><th className="py-2 pr-3">{t('admin.thUser')}</th><th className="py-2 pr-3">{t('admin.thRole')}</th><th className="py-2 pr-3">{t('admin.thCreated')}</th><th className="py-2 text-right">{t('admin.thActions')}</th></tr></thead><tbody>{users.map(user => <tr key={user.id} className="border-b last:border-0 dark:border-gray-800"><td className="py-3 pr-3"><div className="font-medium text-gray-900 dark:text-gray-100">{user.name}</div><div className="text-xs text-gray-500">{user.email}</div></td><td className="py-3 pr-3"><span className={`px-2 py-1 rounded-full text-xs ${user.role === 'admin' ? 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'}`}>{t(`role.${user.role}`)}</span></td><td className="py-3 pr-3 text-gray-500">{dateLabel(user.created_at)}</td><td className="py-3 text-right"><div className="inline-flex gap-2"><button disabled={busyUser === user.id || user.id === currentUser.id} onClick={() => changeRole(user)} title={user.id === currentUser.id ? t('admin.noDemote') : t('admin.changeRole')} className="p-2 rounded border dark:border-gray-700 disabled:opacity-40"><ShieldCheck className="w-4 h-4" /></button><button disabled={busyUser === user.id || user.id === currentUser.id} onClick={() => deleteUser(user)} title={t('admin.deleteUser')} className="p-2 rounded border border-red-200 text-red-600 disabled:opacity-40"><Trash2 className="w-4 h-4" /></button></div></td></tr>)}</tbody></table></div></div>
      <div className={cardClass}><div className="flex items-center gap-2 mb-4"><Activity className="w-5 h-5 text-teal-500" /><h3 className="font-semibold text-gray-900 dark:text-white">{t('admin.system')}</h3></div><div className="space-y-4"><Status ok={system.db_connected} label={system.db_connected ? t('admin.dbOk') : t('admin.dbDown')} /><Status ok={system.model_loaded} label={system.model_loaded ? t('admin.modelLoaded') : t('admin.modelNotLoaded')} /><Status ok={system.weights_exists} label={system.weights_exists ? t('admin.weightsOk') : t('admin.weightsMissing')} /><div><div className="flex justify-between text-xs text-gray-500 mb-1"><span className="flex items-center gap-1"><Database className="w-3.5 h-3.5" />{t('admin.storage')}</span><span>{formatBytes(system.storage_used_bytes)} / {formatBytes(system.storage_quota_bytes)}</span></div><div className="h-2 rounded-full bg-gray-200 dark:bg-gray-800"><div className="h-2 rounded-full bg-teal-500" style={{ width: `${ratio}%` }} /></div></div><p className="text-xs text-gray-500 dark:text-gray-400">{t('admin.storageNote')}</p></div></div>
    </div>

    <div className={cardClass}><div className="flex items-center gap-2 mb-4"><BarChart3 className="w-5 h-5 text-teal-500" /><h3 className="font-semibold text-gray-900 dark:text-white">{t('admin.allAnalyses')}</h3><span className="ml-auto text-xs text-gray-500">{t('admin.latest500')}</span></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase text-gray-500 border-b dark:border-gray-700"><th className="py-2">{t('admin.thFile')}</th><th className="py-2">{t('admin.thOwner')}</th><th className="py-2">{t('admin.thType')}</th><th className="py-2">{t('admin.thResult')}</th><th className="py-2">{t('admin.thDate')}</th></tr></thead><tbody>{analyses.map(item => <tr key={item.id} className="border-b last:border-0 dark:border-gray-800"><td className="py-3 max-w-[230px] truncate text-gray-900 dark:text-gray-100">{item.filename}</td><td className="py-3 text-gray-600 dark:text-gray-300">{item.user?.name || t('admin.deletedAccount')}</td><td className="py-3">{item.media_type === 'video' ? <Video className="w-4 h-4 text-purple-500" /> : <ImageIcon className="w-4 h-4 text-blue-500" />}</td><td className="py-3">{item.has_bug ? <span className="text-red-600">{t('admin.bugs', { n: item.num_detections })}</span> : <span className="text-emerald-600">{t('admin.clean')}</span>}</td><td className="py-3 text-gray-500">{dateLabel(item.timestamp)}</td></tr>)}</tbody></table>{analyses.length === 0 && <p className="py-8 text-center text-sm text-gray-500">{t('admin.none')}</p>}</div></div>
  </section>;
}
