import { useCallback, useEffect, useRef, useState } from 'react';
import {
  History, AlertTriangle, CheckCircle, Image as ImageIcon, Video, Search, Trash2, Loader2,
} from 'lucide-react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useToast } from '../ToastContext';

const PAGE_SIZE = 20;

/**
 * Self-fetching analysis history: server-side search, status/type filters,
 * "load more" pagination and per-row delete.
 *
 * `refreshKey` changes whenever a new analysis finished (refetch from the top);
 * `onChanged` is called after a delete so the parent can refresh its stats.
 */
export default function HistoryTable({ refreshKey = 0, onChanged }) {
  const { t, formatShort } = useI18n();
  const toast = useToast();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [type, setType] = useState('');
  const [deletingId, setDeletingId] = useState(null);
  const latestRequest = useRef(0);

  // Debounce the search box so we don't hit the API on every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchPage = useCallback(async (offset, append) => {
    const requestId = ++latestRequest.current;
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const data = await api.history({
        limit: PAGE_SIZE,
        offset,
        ...(query && { q: query }),
        ...(status && { status }),
        ...(type && { type }),
      });
      if (requestId !== latestRequest.current) return; // a newer request superseded this one
      const rows = data.predictions || [];
      setItems((current) => (append ? [...current, ...rows] : rows));
      setTotal(data.total ?? rows.length);
    } catch (e) {
      if (requestId === latestRequest.current) {
        toast.error(e.response?.data?.error || { key: 'history.loadFailed' });
      }
    } finally {
      if (requestId === latestRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [query, status, type, toast]);

  useEffect(() => {
    fetchPage(0, false);
  }, [fetchPage, refreshKey]);

  const handleDelete = async (item) => {
    if (!window.confirm(t('history.confirmDelete', { file: item.filename }))) return;
    setDeletingId(item.id);
    try {
      await api.deleteAnalysis(item.id);
      setItems((current) => current.filter((row) => row.id !== item.id));
      setTotal((n) => Math.max(0, n - 1));
      toast.success({ key: 'history.deleted' });
      if (onChanged) onChanged();
    } catch (e) {
      toast.error(e.response?.data?.error || { key: 'history.deleteFailed' });
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = Boolean(query || status || type);

  const header = (
    <h2 className="panel-title">
      <span className="panel-icon"><History className="w-4 h-4" /></span> {t('history.title')}
      {total > 0 && <span className="bs-mono ml-auto text-[10px] font-normal opacity-60">{total}</span>}
    </h2>
  );

  const filters = (
    <div className="mb-3 flex flex-wrap gap-2">
      <label className="relative min-w-[8rem] flex-1">
        <span className="sr-only">{t('history.search')}</span>
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 opacity-50" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('history.searchPh')}
          className="field w-full pl-7"
        />
      </label>
      <select
        className="field"
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        aria-label={t('history.filterStatus')}
      >
        <option value="">{t('history.allStatus')}</option>
        <option value="bug">{t('history.onlyBugs')}</option>
        <option value="clean">{t('history.onlyClean')}</option>
      </select>
      <select
        className="field"
        value={type}
        onChange={(e) => setType(e.target.value)}
        aria-label={t('history.filterType')}
      >
        <option value="">{t('history.allTypes')}</option>
        <option value="image">{t('history.onlyImages')}</option>
        <option value="video">{t('history.onlyVideos')}</option>
      </select>
    </div>
  );

  if (loading && items.length === 0) {
    return (
      <div className="panel panel-enter">
        {header}
        {filters}
        <div className="empty-state">
          <Loader2 className="w-6 h-6 animate-spin opacity-50" />
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="panel panel-enter">
        {header}
        {(filtered || total > 0) && filters}
        <div className="empty-state">
          <History className="w-8 h-8 opacity-40" />
          {filtered ? t('history.noMatch') : t('history.empty')}
        </div>
      </div>
    );
  }

  return (
    <div className="panel panel-enter">
      {header}
      {filters}
      <div className={`overflow-x-auto max-h-96 overflow-y-auto -mx-2 px-2 transition-opacity ${loading ? 'opacity-60' : ''}`}>
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white/95 dark:bg-[#0D1219]/95 backdrop-blur">
            <tr className="border-b border-[#DCE6E8] dark:border-[#1E2733] text-left">
              {['history.time', 'history.type', 'history.file', 'history.status', 'history.det'].map((h) => (
                <th key={h} className={`pb-2 tile-label font-medium ${h === 'history.det' ? 'text-right' : ''}`}>{t(h)}</th>
              ))}
              <th className="pb-2"><span className="sr-only">{t('history.actions')}</span></th>
            </tr>
          </thead>
          <tbody>
            {items.map((h) => {
              const isVideo = h.media_type === 'video';
              return (
                <tr key={h.id} className="border-b border-[#EEF3F4] dark:border-[#161D28] hover:bg-teal-500/5 dark:hover:bg-teal-300/5 transition-colors">
                  <td className="py-2.5 pr-2 text-[#5B6B74] dark:text-gray-400 text-xs bs-mono whitespace-nowrap">
                    {formatShort(h.timestamp)}
                  </td>
                  <td className="py-2.5">
                    <span
                      className="grid h-6 w-6 place-items-center rounded-md bg-[#F4F7F7] text-[#5B6B74] dark:bg-[#111826] dark:text-gray-400"
                      title={isVideo ? t('history.typeVideo') : t('history.typeImage')}
                    >
                      {isVideo ? <Video className="w-3.5 h-3.5" /> : <ImageIcon className="w-3.5 h-3.5" />}
                    </span>
                  </td>
                  <td className="py-2.5 bs-mono text-xs text-[#0F1B24] dark:text-gray-300 truncate max-w-32" title={h.filename}>
                    {h.filename}
                  </td>
                  <td className="py-2.5">
                    {h.has_bug ? (
                      <span className="badge badge-bug">
                        <AlertTriangle className="w-3 h-3" />
                        {isVideo ? t('history.frames', { n: h.video_summary?.buggy_frames ?? '?' }) : t('history.bug')}
                      </span>
                    ) : (
                      <span className="badge badge-ok">
                        <CheckCircle className="w-3 h-3" /> {t('history.clean')}
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 text-right bs-mono text-[#0F1B24] dark:text-gray-300">
                    {h.num_detections}
                  </td>
                  <td className="py-2.5 pl-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleDelete(h)}
                      disabled={deletingId === h.id}
                      title={t('history.delete')}
                      aria-label={`${t('history.delete')}: ${h.filename}`}
                      className="rounded p-1 text-[#5B6B74] transition-colors hover:bg-red-500/10 hover:text-red-500 disabled:opacity-40 dark:text-gray-500"
                    >
                      {deletingId === h.id
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        : <Trash2 className="w-3.5 h-3.5" />}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-[#5B6B74] dark:text-gray-500">
        <span>{t('history.showing', { shown: items.length, total })}</span>
        {items.length < total && (
          <button
            type="button"
            onClick={() => fetchPage(items.length, true)}
            disabled={loadingMore}
            className="btn-secondary !w-auto !py-1.5 !text-xs"
          >
            {loadingMore && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {t('history.loadMore')}
          </button>
        )}
      </div>
    </div>
  );
}
