import { useState } from 'react';
import { Film, Image as ImageIcon, ScanSearch } from 'lucide-react';
import { useI18n } from '../i18n';
import UploadPanel from './UploadPanel';
import VideoAnalysis from './VideoAnalysis';

const TABS = [
  { id: 'image', labelKey: 'analyze.tabImage', Icon: ImageIcon },
  { id: 'video', labelKey: 'analyze.tabVideo', Icon: Film },
];

/** One "new analysis" card: tabs switch between the screenshot and video forms. */
export default function AnalyzePanel({ onPredict, loading, onVideoReport }) {
  const { t } = useI18n();
  const [tab, setTab] = useState('image');

  return (
    <section className="panel panel-enter" aria-labelledby="analyze-title">
      <h2 id="analyze-title" className="panel-title">
        <span className="panel-icon"><ScanSearch className="h-4 w-4" /></span> {t('analyze.title')}
      </h2>

      <div className="seg seg--full mb-5" role="tablist" aria-label={t('analyze.tabs')}>
        {TABS.map(({ id, labelKey, Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`tabpanel-${id}`}
            className="seg__btn"
            onClick={() => setTab(id)}
          >
            <Icon className="h-4 w-4" /> {t(labelKey)}
          </button>
        ))}
      </div>

      {/* Both forms stay mounted so a chosen file / settings survive a tab switch. */}
      <div role="tabpanel" id="tabpanel-image" aria-labelledby="tab-image" hidden={tab !== 'image'}>
        <UploadPanel onPredict={onPredict} loading={loading} />
      </div>
      <div role="tabpanel" id="tabpanel-video" aria-labelledby="tab-video" hidden={tab !== 'video'}>
        <VideoAnalysis onVideoReport={onVideoReport} hideResult />
      </div>
    </section>
  );
}
