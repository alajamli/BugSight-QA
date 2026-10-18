import { useCallback, useEffect, useRef, useState } from 'react';
import {
  History, AlertTriangle, CheckCircle, Image as ImageIcon, Video, Search, Trash2, Loader2, X,
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

  const resetFilters = () => {
    setSearch('');
    setStatus('');
    setType('');
  };

  const segment = (label, current, setCurrent, options) => (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([value, text]) => (
        <button
          key={value || 'all'}
          type="button"
          className="seg__btn"
          aria-pressed={current === value}
          onClick={() => setCurrent(value)}
        >
          {text}
        </button>
      ))}
    </div>
  );

  const filters = (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <label className="relative min-w-[12rem] flex-1">
        <span className="sr-only">{t('history.search')}</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 opacity-50" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('history.searchPh')}
          className="field w-full !pl-9"
        />
      </label>
      {segment(t('history.filterStatus'), status, setStatus, [
        ['', t('history.allStatus')],
        ['bug', t('history.onlyBugs')],
        ['clean', t('history.onlyClean')],
      ])}
      {segment(t('history.filterType'), type, setType, [
        ['', t('history.allTypes')],
        ['image', t('history.onlyImages')],
        ['video', t('history.onlyVideos')],
      ])}
      {filtered && (
        <button type="button" className="btn-ghost" onClick={resetFilters}>
          <X className="h-3.5 w-3.5" /> {t('history.reset')}
        </button>
      )}
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
      <div className={`max-h-[26rem] overflow-auto rounded-xl border border-[#E3EBED] transition-opacity dark:border-[#1E2733] ${loading ? 'opacity-60' : ''}`}>
        <table className="tbl">
          <thead>
            <tr>
              <th>{t('history.time')}</th>
              <th>{t('history.type')}</th>
              <th>{t('history.file')}</th>
              <th>{t('history.status')}</th>
              <th className="num">{t('history.det')}</th>
              <th><span className="sr-only">{t('history.actions')}</span></th>
            </tr>
          </thead>
          <tbody>
            {items.map((h) => {
              const isVideo = h.media_type === 'video';
              return (
                <tr key={h.id}>
                  <td className="bs-mono whitespace-nowrap text-xs text-[#5B6B74] dark:text-gray-400">{formatShort(h.timestamp)}</td>
                  <td>
                    <span
                      className="inline-flex items-center gap-1.5 text-xs text-[#5B6B74] dark:text-gray-400"
                      title={isVideo ? t('history.typeVideo') : t('history.typeImage')}
                    >
                      <span className="grid h-6 w-6 place-items-center rounded-md bg-[#F4F7F7] dark:bg-[#111826]">
                        {isVideo ? <Video className="h-3.5 w-3.5" /> : <ImageIcon className="h-3.5 w-3.5" />}
                      </span>
                      <span className="hidden sm:inline">{isVideo ? t('analyze.tabVideo') : t('analyze.tabImage')}</span>
                    </span>
                  </td>
                  <td className="bs-mono max-w-[16rem] truncate text-xs" title={h.filename}>{h.filename}</td>
                  <td>
                    {h.has_bug ? (
                      <span className="badge badge-bug">
                        <AlertTriangle className="h-3 w-3" />
                        {isVideo ? t('history.frames', { n: h.video_summary?.buggy_frames ?? '?' }) : t('history.bug')}
                      </span>
                    ) : (
                      <span className="badge badge-ok">
                        <CheckCircle className="h-3 w-3" /> {t('history.clean')}
                      </span>
                    )}
                  </td>
                  <td className="num bs-mono">{h.num_detections}</td>
                  <td className="num">
                    <button
                      type="button"
                      onClick={() => handleDelete(h)}
                      disabled={deletingId === h.id}
                      title={t('history.delete')}
                      aria-label={`${t('history.delete')}: ${h.filename}`}
                      className="icon-btn ml-auto"
                    >
                      {deletingId === h.id
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <Trash2 className="h-3.5 w-3.5" />}
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
