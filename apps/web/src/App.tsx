import { useEffect, useState } from 'react';
import {
  Boxes,
  LayoutDashboard,
  WandSparkles,
  Library,
  Network,
  ScanLine,
  Play,
  Settings,
  Layers,
  ChevronDown,
  Plus,
  Minus,
  RotateCcw,
  Save,
  Upload,
  Check,
  ArrowUpRight,
  PanelRightClose,
  Search,
  Download,
  Move,
  Image as ImageIcon,
  Code,
  Activity,
  CheckCircle2,
  AlertCircle,
  LoaderCircle,
} from 'lucide-react';
import type { Asset, MapResult } from '../../../packages/shared/types';
import { overlays as allOverlays } from '../../../packages/shared/types';
import { api } from './api';
import { MapCanvas } from './MapCanvas';

const NAV = [
  ['Dashboard', LayoutDashboard],
  ['Map generator', WandSparkles],
  ['Asset library', Library],
  ['Scene planner', Network],
  ['Layout inspector', ScanLine],
  ['Play mode', Play],
  ['Settings', Settings],
] as const;
const concepts = [
  'Tavern',
  'Bedroom',
  'Library',
  'Kitchen',
  'Office',
  'Shop',
  'Hospital',
  'Blacksmith',
  'Laboratory',
  'Spaceship',
];
const initialDescription =
  'A welcoming medieval tavern with an oak dining table, a candlelit service counter, and a small storage area. Keep clear paths between each area.';
function pretty(v: any) {
  return JSON.stringify(v, null, 2);
}
function download(value: any, name: string) {
  const url = URL.createObjectURL(new Blob([pretty(value)], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function App() {
  const [tab, setTab] = useState('Map generator');
  const [status, setStatus] = useState<any>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [maps, setMaps] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [description, setDescription] = useState(initialDescription);
  const [width, setWidth] = useState(28);
  const [height, setHeight] = useState(24);
  const [seed, setSeed] = useState(1042);
  const [density, setDensity] = useState(0.5);
  const [decoration, setDecoration] = useState(0.5);
  const [candidates, setCandidates] = useState(4);
  const [map, setMap] = useState<MapResult | null>(null);
  const [sceneText, setSceneText] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [failed, setFailed] = useState<any>(null);
  const [reference, setReference] = useState<any>(null);
  const [live, setLive] = useState(false);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [zoom, setZoom] = useState(1);
  const [play, setPlay] = useState(false);
  const [stage, setStage] = useState('Final map');
  const [selected, setSelected] = useState('');
  const [query, setQuery] = useState('');
  const [assetEditor, setAssetEditor] = useState<Asset | null>(null);
  const [assetText, setAssetText] = useState('');
  const [settings, setSettings] = useState<any>(null);
  const [usage, setUsage] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [weights, setWeights] = useState({
    organization: 0.25,
    relationships: 0.25,
    navigation: 0.2,
    composition: 0.15,
    reference: 0.1,
    decoration: 0.05,
  });
  async function refresh() {
    const [s, a, m, h, st, u] = await Promise.all([
      api('/health'),
      api('/assets'),
      api('/maps'),
      api('/history'),
      api('/settings'),
      api('/usage'),
    ]);
    setStatus(s);
    setAssets(a);
    setMaps(m);
    setHistory(h);
    setSettings(st);
    setUsage(u);
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  async function generate(useScene = false, newSeed = seed) {
    setError('');
    setNotice('');
    setFailed(null);
    setBusy(useScene ? 'Validating scene graph…' : 'Planning functional areas…');
    try {
      let scene;
      if (useScene) scene = JSON.parse(sceneText);
      else {
        const result = await api('/plan', {
          description,
          density,
          decorationDensity: decoration,
          mode: live ? 'live' : 'mock',
          ...(reference ? { referenceId: reference.id } : {}),
        });
        scene = result.scene;
        setSceneText(pretty(scene));
        setNotice(result.notice || `Semantic scene planned with ${result.model}.`);
      }
      setBusy('Assembling groups and validating routes…');
      const result = await api('/generate', {
        scene,
        width,
        height,
        seed: newSeed,
        candidates,
        density,
        decorationDensity: decoration,
        weights,
      });
      if (!result.ok) {
        setFailed(result.diagnostics);
        setError('No valid layout found. Inspect the failed constraints below.');
        setMap(null);
      } else {
        setMap(result);
        setSelected('');
        setStage('Final map');
        setSeed(newSeed);
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy('Uploading reference…');
    setError('');
    try {
      const body = new FormData();
      body.append('image', file);
      setReference(await api('/references', body));
      setNotice('Reference stored. Live vision planning requires a configured OpenRouter model.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  async function save() {
    if (!map) return;
    setBusy('Validating and saving…');
    try {
      await api('/maps', { result: map });
      setNotice('Map saved with its scene, seed, configuration, and asset metadata snapshot.');
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  async function load(id: string) {
    try {
      const saved = await api('/maps/' + id);
      const report = await api('/validate', {
        request: saved.result.reproduction,
        layout: saved.result.layout,
      });
      if (!report.valid) throw new Error('Saved map failed current validation');
      setMap({ ...saved.result, validation: report });
      setSceneText(pretty(saved.result.scene));
      setSeed(saved.result.layout.seed);
      setWidth(saved.result.layout.width);
      setHeight(saved.result.layout.height);
      setTab('Map generator');
      setError('');
      setNotice('Saved map loaded and revalidated.');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function move(id: string, x: number, y: number) {
    if (!map) return;
    const p = map.layout.placements.find((v) => v.id === id)!;
    const dx = x - p.x,
      dy = y - p.y;
    const layout = {
      ...map.layout,
      placements: map.layout.placements.map((v) =>
        v.groupId === p.groupId ? { ...v, x: v.x + dx, y: v.y + dy } : v,
      ),
    };
    try {
      const validation = await api('/validate', { request: map.reproduction, layout });
      if (!validation.valid) {
        setError(`Move rejected: ${validation.failures[0].message}`);
        return;
      }
      setMap({ ...map, layout, validation });
      setNotice(
        'Group moved together; collision, relationship and navigation checks passed. Generation scores describe the original candidate.',
      );
      setError('');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const diagnostics = map?.diagnostics || failed;
  const score = map?.diagnostics.candidates.find(
    (c: any) => c.index === map.diagnostics.selectedCandidate,
  )?.score;
  const chosen = map?.layout.placements.find((p) => p.id === selected);
  const chosenAsset = map?.assets.find((a) => a.id === chosen?.assetId);
  const toggle = (name: string) =>
    setEnabled((e) => (e.includes(name) ? e.filter((v) => v !== name) : [...e, name]));
  const navigate = (name: string) => {
    setTab(name);
    setPlay(name === 'Play mode');
    if (name === 'Layout inspector') setEnabled(['Zones', 'Collision', 'Circulation']);
  };
  const canvas = map ? (
    <MapCanvas
      map={map}
      play={play}
      overlays={enabled}
      zoom={zoom}
      stage={stage}
      onSelect={setSelected}
      onMove={move}
      onInteract={setNotice}
    />
  ) : (
    <div className="empty-map">
      <div className="empty-icon">
        <Boxes size={42} />
      </div>
      <h2>A world, waiting to take shape.</h2>
      <p>
        Describe an interior. We’ll give every object
        <br />a place, and every character a way through.
      </p>
      <button className="primary" disabled={!!busy} onClick={() => generate()}>
        <WandSparkles size={16} /> Generate your first room
      </button>
      <span>Deterministic placement · No AI key needed</span>
    </div>
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate('Dashboard');
          }}
        >
          <span className="brand-mark">
            <Boxes size={25} />
          </span>
          <span>
            infiniture<small>WORLD BUILDING STUDIO</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">I</span>
          <div>
            Interior sandbox<small>Local workspace</small>
          </div>
          <ChevronDown size={15} />
        </div>
        <span className="nav-caption">WORKSPACE</span>
        <nav>
          {NAV.map(([name, Icon]) => (
            <button
              key={name}
              className={tab === name ? 'active' : ''}
              onClick={() => navigate(name)}
            >
              <Icon size={18} />
              {name}
              {name === 'Asset library' && <span className="nav-count">{assets.length || 32}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-badge">
            <span className={status?.engine === 'online' ? 'status-dot' : 'status-dot off'} />
            <span>{status?.engine === 'online' ? 'Engine online' : 'Engine not connected'}</span>
          </div>
          <p>Built for worlds worth exploring.</p>
          <div className="version">
            PROTOTYPE <span>v0.1.0</span>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{tab}</strong>
          </div>
          <div className="top-actions">
            <span className="pill">{live ? 'OpenRouter planner' : 'Offline semantic planner'}</span>
            <button
              className="icon-btn"
              aria-label="Refresh system status"
              onClick={() => refresh().catch((e) => setError(e.message))}
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </header>
        <div className="page-heading">
          <div>
            <div className="eyebrow">CREATE A PLACE, NOT JUST A PICTURE</div>
            <h1>{tab === 'Map generator' ? 'Interior map generator' : tab}</h1>
            <p>
              {tab === 'Map generator'
                ? 'Turn an idea into a coherent, playable little world.'
                : 'Build, inspect, and explore your procedural interiors.'}
            </p>
          </div>
          <div className="heading-actions">
            {map && (
              <>
                <button onClick={() => download(map, `infiniture-${map.layout.seed}.json`)}>
                  <Download size={15} /> Export
                </button>
                <button onClick={save} disabled={!!busy}>
                  <Save size={15} /> Save map
                </button>
              </>
            )}
          </div>
        </div>
        {(error || notice || status?.warning) && (
          <div className={'banner ' + (error ? 'error' : '')} role="status">
            {error ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
            <span>{error || notice || status?.warning}</span>
            <button
              onClick={() => {
                setError('');
                setNotice('');
              }}
              aria-label="Dismiss message"
            >
              ×
            </button>
          </div>
        )}
        {['Map generator', 'Layout inspector', 'Play mode'].includes(tab) && (
          <div className={'generator-layout ' + (tab === 'Play mode' ? 'wide-preview' : '')}>
            {tab !== 'Play mode' && (
              <section className="config-panel">
                <div className="panel-heading">
                  <h2>{tab === 'Layout inspector' ? 'Inspector controls' : 'Room brief'}</h2>
                  <span className="tiny-label">
                    {tab === 'Layout inspector' ? 'DEBUG' : 'INPUT'}
                  </span>
                </div>
                {tab === 'Map generator' ? (
                  <>
                    <label className="field-label" htmlFor="description">
                      What are we building?
                    </label>
                    <textarea
                      id="description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Describe your interior…"
                    />
                    <div className="concepts">
                      {concepts.slice(0, 5).map((c) => (
                        <button
                          key={c}
                          onClick={() =>
                            setDescription(
                              `A ${c.toLowerCase()} with distinct functional zones, coherent furniture groups and clear walking paths.`,
                            )
                          }
                        >
                          {c}
                        </button>
                      ))}
                    </div>
                    <label className="upload-zone">
                      <input
                        type="file"
                        accept="image/png,image/jpeg"
                        onChange={(e) => upload(e.target.files?.[0])}
                      />
                      {reference ? (
                        <img src={reference.url} alt="Uploaded interior reference" />
                      ) : (
                        <ImageIcon size={23} />
                      )}
                      <strong>{reference ? 'Reference attached' : 'Add a reference image'}</strong>
                      <span>PNG or JPG · up to 8 MB</span>
                    </label>
                    <div className="section-rule" />
                    <h3>Room configuration</h3>
                    <div className="field-pair">
                      <label>
                        Width <span>tiles</span>
                        <input
                          type="number"
                          min="12"
                          max="64"
                          value={width}
                          onChange={(e) => setWidth(+e.target.value)}
                        />
                      </label>
                      <label>
                        Height <span>tiles</span>
                        <input
                          type="number"
                          min="12"
                          max="64"
                          value={height}
                          onChange={(e) => setHeight(+e.target.value)}
                        />
                      </label>
                    </div>
                    <label className="range-label">
                      Furniture density <strong>{Math.round(density * 100)}%</strong>
                      <input
                        type="range"
                        min="10"
                        max="100"
                        value={density * 100}
                        onChange={(e) => setDensity(+e.target.value / 100)}
                      />
                      <span>
                        Spacious <i /> Furnished
                      </span>
                    </label>
                    <label className="range-label">
                      Decoration density <strong>{Math.round(decoration * 100)}%</strong>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={decoration * 100}
                        onChange={(e) => setDecoration(+e.target.value / 100)}
                      />
                    </label>
                    <label>
                      Visual style
                      <select value="hearth_pixel" onChange={() => {}}>
                        <option value="hearth_pixel">Hearth · original pixel art</option>
                      </select>
                    </label>
                    <div className="field-pair">
                      <label>
                        Generation seed
                        <input
                          type="number"
                          min="0"
                          max="2147483647"
                          value={seed}
                          onChange={(e) => setSeed(+e.target.value)}
                        />
                      </label>
                      <label>
                        Candidates
                        <input
                          type="number"
                          min="1"
                          max="12"
                          value={candidates}
                          onChange={(e) => setCandidates(+e.target.value)}
                        />
                      </label>
                    </div>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={live}
                        onChange={(e) => setLive(e.target.checked)}
                      />{' '}
                      Use live AI planning
                    </label>
                    <button
                      className="primary full"
                      disabled={!!busy || !description.trim()}
                      onClick={() => generate()}
                    >
                      {busy ? (
                        <LoaderCircle className="spin" size={17} />
                      ) : (
                        <WandSparkles size={17} />
                      )}{' '}
                      {busy ? 'Building interior…' : 'Generate interior'}
                    </button>
                    <p className="helper">
                      AI proposes the concept.
                      <br />
                      The spatial engine makes it playable.
                    </p>
                  </>
                ) : (
                  <>
                    <label>
                      Pipeline stage
                      <select value={stage} onChange={(e) => setStage(e.target.value)}>
                        {['Architecture', 'Zones', 'Final map'].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                    <h3>Debug overlays</h3>
                    <div className="overlay-list">
                      {allOverlays.map((name) => (
                        <label className="check-label" key={name}>
                          <input
                            type="checkbox"
                            checked={enabled.includes(name)}
                            onChange={() => toggle(name)}
                          />
                          {name}
                        </label>
                      ))}
                    </div>
                    <button onClick={() => setEnabled([])}>Clear overlays</button>
                  </>
                )}
              </section>
            )}
            <section className="preview-section">
              <div className="preview-card">
                <div className="preview-toolbar">
                  <div className="preview-title">
                    <span className="status-dot" />
                    <strong>{map?.scene.title || 'Interior preview'}</strong>
                    {map && (
                      <span className="muted">
                        {map.layout.width} × {map.layout.height}
                      </span>
                    )}
                  </div>
                  <div className="segmented">
                    <button className={!play ? 'selected' : ''} onClick={() => setPlay(false)}>
                      <Move size={13} /> Editor
                    </button>
                    <button
                      className={play ? 'selected' : ''}
                      onClick={() => {
                        setPlay(true);
                        setStage('Final map');
                      }}
                    >
                      <Play size={13} /> Play
                    </button>
                  </div>
                </div>
                <div className="viewport">
                  {canvas}
                  <div className="viewport-top">
                    <span className="canvas-tag">
                      {map ? '16 PX / TILE' : 'PROCEDURAL PREVIEW'}
                    </span>
                    <span className="canvas-tag">ORIGINAL PLACEHOLDER ART</span>
                  </div>
                  {busy && (
                    <div className="loading-cover">
                      <LoaderCircle className="spin" size={26} />
                      <p>{busy}</p>
                    </div>
                  )}
                  <div className="viewport-bottom">
                    <span>
                      {play
                        ? 'Click map · WASD to walk · E to interact'
                        : map
                          ? 'Drag a group to adjust · click an object to inspect'
                          : 'Your generated room will appear here'}
                    </span>
                    <div className="zoom-controls">
                      <button
                        aria-label="Zoom out"
                        onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
                      >
                        <Minus size={14} />
                      </button>
                      <button onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
                      <button
                        aria-label="Zoom in"
                        onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                  </div>
                </div>
                <div className="preview-footer">
                  <div className="overlay-chips">
                    {['Grid', 'Zones', 'Collision', 'Paths'].map((name) => (
                      <button
                        key={name}
                        className={enabled.includes(name) ? 'on' : ''}
                        onClick={() => toggle(name)}
                      >
                        <span />
                        {name}
                      </button>
                    ))}
                  </div>
                  <button
                    className="text-btn"
                    disabled={!map || !!busy}
                    onClick={() => generate(true, seed + 1)}
                  >
                    <RotateCcw size={13} /> Regenerate
                  </button>
                </div>
              </div>
              <div className="diagnostic-strip">
                <div>
                  <span>LAYOUT QUALITY</span>
                  <strong>
                    {score ? `${score.total.toFixed(1)}` : '—'}
                    <small>/ 100</small>
                  </strong>
                </div>
                <div>
                  <span>HARD CONSTRAINTS</span>
                  <strong className={map ? 'mint' : ''}>
                    {map ? (
                      <>
                        <Check size={16} /> Passed
                      </>
                    ) : (
                      '—'
                    )}
                  </strong>
                </div>
                <div>
                  <span>ACCESSIBLE TARGETS</span>
                  <strong>
                    {map
                      ? `${map.validation.interactions.filter((i) => i.reachable).length} / ${map.validation.interactions.length}`
                      : '—'}
                  </strong>
                </div>
                <div>
                  <span>GENERATION TIME</span>
                  <strong>{diagnostics ? `${Math.round(diagnostics.durationMs)} ms` : '—'}</strong>
                </div>
              </div>
              <div className="below-preview">
                <section className="mini-panel">
                  <div className="panel-heading">
                    <h2>
                      <Layers size={16} /> Functional zones
                    </h2>
                    <span className="tiny-label">{map?.scene.zones.length || 0} ZONES</span>
                  </div>
                  {map ? (
                    <div className="zone-list">
                      {map.scene.zones.map((z: any, i: number) => (
                        <div key={z.id}>
                          <span className={'zone-dot zone-' + i} />
                          <span>
                            {z.purpose}
                            <small>
                              {map.layout.zones[z.id]?.width} × {map.layout.zones[z.id]?.height}{' '}
                              tiles
                            </small>
                          </span>
                          <span className="zone-state">Connected</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-note">Functional areas are allocated before furniture.</p>
                  )}
                </section>
                <section className="mini-panel">
                  <div className="panel-heading">
                    <h2>
                      <Activity size={16} /> Generation report
                    </h2>
                    <span className="tiny-label">
                      {diagnostics ? `SEED ${diagnostics.seed}` : 'READY'}
                    </span>
                  </div>
                  {diagnostics ? (
                    <>
                      <div className="report-line">
                        <span>Valid candidates</span>
                        <strong>
                          {diagnostics.valid} / {diagnostics.attempted}
                        </strong>
                      </div>
                      <div className="report-line">
                        <span>Required furniture placed</span>
                        <strong>
                          {map
                            ? `${Math.round(diagnostics.requiredPlacementRate * 100)}%`
                            : 'No accepted map'}
                        </strong>
                      </div>
                      <div className="report-line">
                        <span>Selected candidate</span>
                        <strong>{map ? `#${diagnostics.selectedCandidate + 1}` : 'None'}</strong>
                      </div>
                      <button
                        className="text-btn"
                        onClick={() => {
                          setTab('Layout inspector');
                          setEnabled(['Collision', 'Paths']);
                        }}
                      >
                        Inspect generation <ScanLine size={13} />
                      </button>
                    </>
                  ) : (
                    <p className="empty-note">
                      Every accepted map is checked for overlap, clearance, relationships and
                      reachable interactions.
                    </p>
                  )}
                </section>
              </div>
              {chosen && (
                <section className="mini-panel object-inspector">
                  <h3>
                    {chosenAsset?.name} <span className="muted">{chosen.id}</span>
                  </h3>
                  <div className="report-line">
                    <span>Group</span>
                    <code>{chosen.groupId}</code>
                    <span>Ground position</span>
                    <code>
                      {chosen.x}, {chosen.y}
                    </code>
                    <span>Orientation</span>
                    <code>{chosen.orientation}</code>
                  </div>
                  <p className="helper">
                    Drag any member to move its complete group. Invalid adjustments are rejected.
                  </p>
                </section>
              )}
              {tab === 'Layout inspector' && diagnostics && (
                <section className="mini-panel">
                  <h2>Candidate comparison</h2>
                  <table>
                    <thead>
                      <tr>
                        <th>Candidate</th>
                        <th>Result</th>
                        <th>Score</th>
                        <th>Search nodes</th>
                        <th>Repair</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagnostics.candidates.map((c: any) => (
                        <tr key={c.index}>
                          <td>#{c.index + 1}</td>
                          <td>{c.valid ? 'Valid' : 'Rejected'}</td>
                          <td>{c.score?.total ?? '—'}</td>
                          <td>{c.searchNodes ?? '—'}</td>
                          <td>{c.repairs.length ? 'Optional members removed' : 'None'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <details>
                    <summary>Full diagnostics and failed constraints</summary>
                    <pre>{pretty(diagnostics)}</pre>
                  </details>
                </section>
              )}
              {failed && (
                <section className="mini-panel">
                  <h3>Generation failed</h3>
                  <pre>{pretty(failed.failures)}</pre>
                </section>
              )}
            </section>
          </div>
        )}
        {tab === 'Dashboard' && (
          <div className="content-page">
            <div className="dashboard-stats">
              {[
                ['Saved maps', maps.length],
                ['Generation attempts', history.length],
                ['Accepted generations', history.filter((h) => h.ok).length],
                ['Approved assets', assets.filter((a) => a.approved).length],
              ].map(([label, value]) => (
                <div className="mini-panel" key={label}>
                  <span className="eyebrow">{label}</span>
                  <h2 className="big-stat">{value}</h2>
                </div>
              ))}
            </div>
            <div className="mini-panel">
              <div className="panel-heading">
                <h2>Your saved worlds</h2>
                <button className="primary" onClick={() => navigate('Map generator')}>
                  <Plus size={16} /> New interior
                </button>
              </div>
              {maps.length ? (
                <div className="saved-grid">
                  {maps.map((m) => (
                    <button key={m.id} className="saved-map" onClick={() => load(m.id)}>
                      <Boxes size={32} />
                      <h3>{m.name || m.title}</h3>
                      <p>
                        Seed {m.seed} · {m.score?.toFixed(1)} quality
                      </p>
                      <span>Open map</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="empty-note">
                  Save a generated map to keep its exact scene, layout and asset versions here.
                </p>
              )}
            </div>
            <div className="mini-panel">
              <h2>System status</h2>
              <div className="report-line">
                <span>Python procedural service</span>
                <strong>{status?.engine || 'Checking…'}</strong>
              </div>
              <div className="report-line">
                <span>Persistence</span>
                <strong>{status?.storage || 'Checking…'}</strong>
              </div>
              <div className="report-line">
                <span>OpenRouter key</span>
                <strong>
                  {status?.openrouterConfigured
                    ? 'Configured'
                    : 'Not configured · mock mode available'}
                </strong>
              </div>
            </div>
          </div>
        )}
        {tab === 'Asset library' && (
          <div className="content-page">
            <div className="library-toolbar">
              <label className="search">
                <Search size={17} />
                <input
                  aria-label="Search assets"
                  placeholder="Search name or category…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <span className="pill">32 original placeholder sprites</span>
              <button
                onClick={() => {
                  const template = {
                    ...assets.find((a) => a.id === 'crate'),
                    id: 'custom_asset',
                    name: 'Custom asset',
                    approved: false,
                  };
                  setAssetEditor(template as Asset);
                  setAssetText(pretty(template));
                }}
              >
                Import metadata
              </button>
            </div>
            <div className="asset-grid">
              {assets
                .filter((a) =>
                  (a.name + ' ' + a.category).toLowerCase().includes(query.toLowerCase()),
                )
                .map((a) => (
                  <button
                    className="asset-card"
                    key={a.id}
                    onClick={() => {
                      setAssetEditor(a);
                      setAssetText(pretty(a));
                    }}
                  >
                    <div className="asset-image">
                      <img src={a.sprite} alt={a.name} />
                    </div>
                    <div className="asset-caption">
                      <h3>{a.name}</h3>
                      <span>
                        {a.category.replace('_', ' ')} · {a.footprint.width} × {a.footprint.height}
                      </span>
                      <small className={a.approved ? 'mint' : ''}>
                        {a.approved ? 'Approved test asset' : 'Awaiting review'}
                      </small>
                    </div>
                  </button>
                ))}
            </div>
          </div>
        )}
        {tab === 'Scene planner' && (
          <div className="content-page planner-page">
            <section className="mini-panel">
              <h2>Semantic scene graph</h2>
              <p>
                Zones, groups and relationships define intent. The engine calculates coordinates.
              </p>
              {map?.scene.groups.map((g: any) => (
                <div className="graph-group" key={g.id}>
                  <Network size={18} />
                  <div>
                    <strong>
                      {map.scene.zones.find((z: any) => z.id === g.zoneId)?.purpose} / {g.id}
                    </strong>
                    {g.objects.map((o: any) => (
                      <div className="graph-node" key={o.id}>
                        <span>{o.assetId}</span>
                        <small>
                          {o.id === g.anchorId
                            ? 'Primary anchor'
                            : o.relations.map((r: any) => r.type.replaceAll('_', ' ')).join(', ')}
                        </small>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {!map && (
                <p className="empty-note">Generate a room or paste a valid scene on the right.</p>
              )}
            </section>
            <section className="mini-panel">
              <div className="panel-heading">
                <h2>
                  <Code size={17} /> Scene JSON
                </h2>
                <button
                  onClick={() => {
                    try {
                      download(JSON.parse(sceneText), 'scene.json');
                    } catch {
                      setError('Scene JSON is invalid. Correct it before exporting.');
                    }
                  }}
                  disabled={!sceneText}
                >
                  Export
                </button>
              </div>
              <textarea
                className="code-editor"
                aria-label="Semantic scene JSON"
                value={sceneText}
                onChange={(e) => setSceneText(e.target.value)}
                spellCheck={false}
              />
              <button
                className="primary"
                disabled={!!busy || !sceneText}
                onClick={() => {
                  setTab('Map generator');
                  generate(true);
                }}
              >
                <WandSparkles size={16} /> Generate from this scene
              </button>
            </section>
          </div>
        )}
        {tab === 'Settings' && (
          <div className="content-page settings-page">
            <section className="mini-panel">
              <h2>AI provider</h2>
              <p>
                API keys stay in <code>apps/api/.env</code>. No credentials are sent to the browser.
              </p>
              <div className="report-line">
                <span>OpenRouter</span>
                <strong>
                  {settings?.keyConfigured
                    ? 'Backend key configured'
                    : 'Backend key not configured'}
                </strong>
              </div>
              <div className="report-line">
                <span>Live image generation</span>
                <strong>Disabled during fixed-library validation</strong>
              </div>
              <button
                onClick={async () => {
                  setBusy('Discovering models…');
                  try {
                    setModels(await api('/models'));
                    setNotice('Available model capabilities loaded from OpenRouter.');
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy('');
                  }
                }}
                disabled={!!busy}
              >
                Discover model capabilities
              </button>
              {settings &&
                Object.entries(settings.assignments).map(([role, id]) => (
                  <label key={role}>
                    {role.replace('_', ' ')} model
                    <input
                      list="models"
                      value={String(id)}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          assignments: { ...settings.assignments, [role]: e.target.value },
                        })
                      }
                      placeholder="Provider/model ID"
                    />
                  </label>
                ))}
              <datalist id="models">
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </datalist>
              <button
                className="primary"
                onClick={async () => {
                  try {
                    await api('/settings/models', settings.assignments, 'PUT');
                    setNotice('Model assignments validated and saved.');
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Save model assignments
              </button>
              <p className="helper">
                Image and vision roles are checked against advertised model capabilities. Live
                planning is opt-in in the room brief.
              </p>
            </section>
            <section className="mini-panel">
              <h2>Candidate scoring</h2>
              <p>
                Weights are normalized. Reference similarity is excluded when no reference tags are
                available.
              </p>
              {Object.entries(weights).map(([k, v]) => (
                <label className="range-label" key={k}>
                  {k}
                  <strong>{Math.round(v * 100)}%</strong>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={v * 100}
                    onChange={(e) => setWeights({ ...weights, [k]: +e.target.value / 100 })}
                  />
                </label>
              ))}
              <div className="section-rule" />
              <h2>AI usage</h2>
              <div className="report-line">
                <span>Recorded calls</span>
                <strong>{usage.length}</strong>
              </div>
              <div className="report-line">
                <span>Reported costs</span>
                <strong>
                  {usage.some((u) => u.cost !== null)
                    ? `$${usage.reduce((a, u) => a + (u.cost || 0), 0).toFixed(4)}`
                    : 'Unavailable / no calls'}
                </strong>
              </div>
              <div className="report-line">
                <span>Tokens</span>
                <strong>
                  {usage.reduce((a, u) => a + (u.promptTokens || 0) + (u.completionTokens || 0), 0)}
                </strong>
              </div>
            </section>
          </div>
        )}
        <footer className="page-footer">
          <span>
            INF INITURE <i /> Spatial intelligence, one room at a time.
          </span>
          <span>16 px tiles · 2D top-down · Local prototype</span>
        </footer>
      </main>
      {assetEditor && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Asset metadata editor"
          >
            <div className="panel-heading">
              <h2>{assetEditor.name}</h2>
              <button onClick={() => setAssetEditor(null)}>Close</button>
            </div>
            <p>
              Editing metadata quarantines the asset until it is reviewed again. Collision, anchors,
              sockets, orientations and behaviors are schema validated.
            </p>
            <div className="asset-modal-preview">
              <img src={assetEditor.sprite} alt={assetEditor.name} />
            </div>
            <label>
              Import sprite (PNG)
              <input
                type="file"
                accept="image/png"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  try {
                    const form = new FormData();
                    form.append('image', f);
                    const uploaded = await api('/references', form);
                    const value = JSON.parse(assetText);
                    value.sprite = uploaded.url;
                    value.orientationSprites = Object.fromEntries(
                      value.supportedOrientations.map((o: string) => [o, uploaded.url]),
                    );
                    setAssetText(pretty(value));
                    setNotice(
                      'Sprite uploaded. Set its dimensions, collision footprint and anchors before saving.',
                    );
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              />
            </label>
            <textarea
              className="code-editor"
              aria-label="Asset metadata JSON"
              value={assetText}
              onChange={(e) => setAssetText(e.target.value)}
              spellCheck={false}
            />
            <div className="heading-actions">
              <button
                onClick={async () => {
                  try {
                    const a = JSON.parse(assetText);
                    await api('/assets/' + a.id, a, 'PUT');
                    setNotice('Metadata saved; asset excluded from generation until approved.');
                    setAssetEditor(null);
                    await refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Save for review
              </button>
              <button
                className="primary"
                onClick={async () => {
                  try {
                    await api('/assets/' + assetEditor.id + '/approve', {
                      visualReviewConfirmed: true,
                    });
                    setNotice(
                      'Asset approved after your visual review and automated dimension checks.',
                    );
                    setAssetEditor(null);
                    await refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Confirm visual review & approve saved asset
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
