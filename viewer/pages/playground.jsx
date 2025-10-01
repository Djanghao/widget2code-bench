import { useEffect, useRef, useState } from 'react';
import { Layout, Typography, Button, Upload, message, Empty, Spin, Space, Segmented } from 'antd';
import { InboxOutlined, DeleteOutlined, EyeOutlined, ExperimentOutlined, ThunderboltOutlined, CloudUploadOutlined, MenuFoldOutlined, MenuUnfoldOutlined, PlayCircleOutlined } from '@ant-design/icons';
import PreviewCard from '../components/PreviewCard';
import Link from 'next/link';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;
const { Dragger } = Upload;

export default function Playground() {
  const [mode, setMode] = useState('upload'); // 'upload' | 'live'
  const [files, setFiles] = useState([]);
  const [listStamp, setListStamp] = useState(Date.now());
  const [rendering, setRendering] = useState(false);
  const [siderCollapsed, setSiderCollapsed] = useState(false);
  const [pasteContent, setPasteContent] = useState('');
  const [pasteType, setPasteType] = useState('html');
  const [pasteName, setPasteName] = useState('widget.html');
  const [liveCode, setLiveCode] = useState('');
  const [liveType, setLiveType] = useState('html');
  const [livePng, setLivePng] = useState(null);
  const [liveRendering, setLiveRendering] = useState(false);

  // Reset paste filename when type changes
  useEffect(() => {
    setPasteName((n) => {
      const base = n.replace(/\.(html|jsx|js)$/i, '');
      return `${base || 'widget'}.${pasteType}`;
    });
  }, [pasteType]);

  useEffect(() => {
    // Reset temp folder when page mounts
    const reset = async () => {
      try {
        await fetch('/api/playground/reset', { method: 'POST' });
      } catch (err) {
        console.warn('Playground reset failed:', err);
      }
      await refreshList();
    };
    reset();
  }, []);

  const refreshList = async () => {
    try {
      const r = await fetch('/api/playground/list');
      const d = await r.json();
      setFiles(d.items || []);
      setListStamp(Date.now());
    } catch (err) {
      console.error('list failed', err);
    }
  };

  const onRenderAll = async () => {
    setRendering(true);
    try {
      await fetch('/api/playground/batch-render', { method: 'POST' });
      // Poll for a short while to pick up new PNG files
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 300));
        await refreshList();
        const allHavePng = (filesRef.current || []).every((it) => !!it.png);
        if (allHavePng) break;
      }
    } catch (err) {
      message.error('Render failed');
    } finally {
      setRendering(false);
    }
  };

  const filesRef = useRef(files);
  useEffect(() => { filesRef.current = files; }, [files]);

  const uploadProps = {
    name: 'file',
    multiple: true,
    directory: true,
    action: '/api/playground/upload',
    method: 'POST',
    withCredentials: false,
    // Pass relativePath so server can preserve directory structure
    data: (file) => {
      const anyFile = file.originFileObj || file;
      const rel = anyFile?.webkitRelativePath || anyFile?.relativePath || anyFile?.path || file.name;
      return { relativePath: rel || file.name };
    },
    onChange(info) {
      const { status } = info.file;
      if (status === 'done') {
        // Debounce list refresh a bit
        setTimeout(() => refreshList(), 120);
      } else if (status === 'error') {
        message.error(`${info.file?.name || 'File'} upload failed.`);
      }
    },
    // Hide Ant Design's built-in file list under the uploader
    showUploadList: false,
    // Keep the visual footprint compact while showing progress
    progress: { strokeWidth: 4 },
  };

  const handlePasteSave = async () => {
    const name = (pasteName || '').trim();
    if (!name) {
      message.warning('Please enter a file name');
      return;
    }
    try {
      const extOk = name.endsWith('.html') || name.endsWith('.jsx') || name.endsWith('.js');
      const finalName = extOk ? name : `${name}.${pasteType}`;
      const res = await fetch('/api/playground/save-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file: finalName, content: pasteContent || '' }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d?.error || 'failed');
      message.success('Saved');
      setPasteContent('');
      await refreshList();
    } catch (err) {
      console.error('save-text failed', err);
      message.error('Save failed');
    }
  };

  useEffect(() => {
    if (mode !== 'live') return;
    if (!liveCode.trim()) {
      setLivePng(null);
      return;
    }
    const timer = setTimeout(() => {
      renderLive();
    }, 500);
    return () => clearTimeout(timer);
  }, [liveCode, liveType, mode]);

  const renderLive = async () => {
    const code = liveCode.trim();
    if (!code) {
      setLivePng(null);
      return;
    }
    setLiveRendering(true);
    try {
      const fileName = `live.${liveType}`;
      const saveRes = await fetch('/api/playground/save-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file: fileName, content: code })
      });
      if (!saveRes.ok) throw new Error('Save failed');

      const renderRes = await fetch(`/api/playground/render-one?file=${encodeURIComponent(fileName)}&force=1`);
      const data = await renderRes.json();
      if (renderRes.ok && data.png) {
        setLivePng(`${data.png}?t=${Date.now()}`);
      } else {
        throw new Error(data?.error || 'render failed');
      }
    } catch (err) {
      console.error('Live render failed:', err);
      setLivePng(null);
    } finally {
      setLiveRendering(false);
    }
  };

  const anyRenderable = files.some((f) => !f.png);
  const isUploadMode = mode === 'upload';

  return (
    <Layout className="layout">
      <Header style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 24px', height: 64, flexShrink: 0, lineHeight: 'normal' }}>
        <Button
          type="text"
          icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setSiderCollapsed((v) => !v)}
          aria-label={siderCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{ color: '#fff' }}
        />
        <Title level={4} style={{ color: '#fff', margin: 0, fontWeight: 700 }}>Widget2Code</Title>
        <div style={{ display: 'flex', gap: 8, marginLeft: 16 }}>
          <Link href="/" prefetch passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="default" icon={<EyeOutlined />}>
                Viewer
              </Button>
            </a>
          </Link>
          <Link href="/playground" prefetch passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="primary" icon={<ExperimentOutlined />}>
                Playground
              </Button>
            </a>
          </Link>
        </div>
        <div style={{ flex: 1 }} />
      </Header>
      <Layout hasSider style={{ height: 'calc(100vh - 64px)' }}>
        <Sider
          width={320}
          collapsedWidth={0}
          collapsible
          collapsed={siderCollapsed}
          trigger={null}
          className={`appSider${siderCollapsed ? ' appSiderCollapsed' : ''}`}
        >
          <div className="siderHeader" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 16 }}>
            <Segmented
              value={mode}
              onChange={setMode}
              options={[
                { label: 'Upload', value: 'upload', icon: <CloudUploadOutlined /> },
                { label: 'Paste', value: 'live', icon: <ThunderboltOutlined /> }
              ]}
              block
            />
            <Title level={5} style={{ margin: '8px 0 0 0' }}>{isUploadMode ? 'Add Files' : 'Live Code Editor'}</Title>
          </div>
          <div className="siderScroll" style={{ gap: 12 }}>
            {isUploadMode ? (
              <Dragger {...uploadProps} className="uploadDraggerFixed" style={{ borderRadius: 10 }}>
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">Click or drag files/folder to upload</p>
                <p className="ant-upload-hint">HTML, JSX, and any assets; folder structure preserved</p>
              </Dragger>
            ) : (
              <LiveCodeEditor
                code={liveCode}
                type={liveType}
                onCodeChange={setLiveCode}
                onTypeChange={setLiveType}
              />
            )}
          </div>
        </Sider>
        <Content style={{ padding: 0, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {isUploadMode ? (
            <>
              <div style={{ padding: '16px 24px', borderBottom: '1px solid #eef0f3', background: '#fafafa', display: 'flex', alignItems: 'center', gap: 16, height: 60, flexShrink: 0 }}>
                <Title level={5} style={{ margin: 0 }}>Previews</Title>
                {rendering ? <Spin size="small" /> : null}
                <Space style={{ marginLeft: 'auto' }}>
                  <Button icon={<DeleteOutlined />} onClick={async () => { await fetch('/api/playground/reset', { method: 'POST' }); await refreshList(); }}>Clear</Button>
                  <Button type="primary" icon={<PlayCircleOutlined />} loading={rendering} disabled={!files.length || !anyRenderable} onClick={onRenderAll}>Render All</Button>
                </Space>
              </div>
              <div className={!files.length ? 'center' : ''} style={{ padding: 16, flex: 1, overflowY: 'auto', minHeight: 0 }}>
                {!files.length ? (
                  <Empty description="Upload or paste code to begin" />
                ) : (
                  <div className="grid">
                    {files.map((f) => (
                      <PlaygroundPreviewCard
                        key={f.file}
                        file={f.file}
                        png={f.png}
                        stamp={listStamp}
                        isRendering={rendering}
                      />
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <div style={{ padding: '16px 24px', borderBottom: '1px solid #eef0f3', background: '#fafafa', display: 'flex', alignItems: 'center', gap: 8, height: 60, flexShrink: 0 }}>
                <Title level={5} style={{ margin: 0 }}>Live Preview</Title>
                {liveRendering && <Spin size="small" />}
              </div>
              <div style={{ flex: 1, display: 'flex', alignItems: 'stretch', justifyContent: 'center', background: '#f5f5f5', padding: 16, minHeight: 0 }}>
                <PreviewCard
                  title={`Live Preview (${liveType.toUpperCase()})`}
                  code={liveCode}
                  initialPngUrl={toPlaygroundFileUrl(livePng)}
                  loading={liveRendering && !livePng}
                  renderEmptyMessage={liveCode.trim() ? 'Render failed' : 'Start typing to see live preview'}
                  variant="fill"
                  renderPadding={32}
                  cardStyle={{ width: '100%', maxWidth: '100%' }}
                  showCodeTab={false}
                />
              </div>
            </>
          )}
        </Content>
      </Layout>
    </Layout>
  );
}

function LiveCodeEditor({ code, type, onCodeChange, onTypeChange }) {
  const textareaRef = useRef(null);

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 8, border: '1px solid #d0d7de', overflow: 'hidden' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 12px',
        borderBottom: '1px solid #d0d7de',
        background: '#f6f8fa'
      }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
          <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
          <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => onTypeChange('html')}
            style={{
              padding: '4px 12px',
              fontSize: 12,
              fontWeight: 500,
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              background: type === 'html' ? '#1677ff' : 'transparent',
              color: type === 'html' ? '#fff' : '#586069',
              transition: 'all 0.2s'
            }}
          >
            HTML
          </button>
          <button
            onClick={() => onTypeChange('jsx')}
            style={{
              padding: '4px 12px',
              fontSize: 12,
              fontWeight: 500,
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              background: type === 'jsx' ? '#1677ff' : 'transparent',
              color: type === 'jsx' ? '#fff' : '#586069',
              transition: 'all 0.2s'
            }}
          >
            JSX
          </button>
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0, background: '#fff' }}>
        <textarea
          ref={textareaRef}
          value={code}
          onChange={(e) => onCodeChange(e.target.value)}
          placeholder={`Paste your ${type.toUpperCase()} code here...`}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            outline: 'none',
            resize: 'none',
            fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontSize: 13,
            lineHeight: 1.6,
            padding: 16,
            background: '#fff',
            color: '#24292f',
            margin: 0,
            overflow: 'auto'
          }}
          spellCheck={false}
        />
      </div>
    </div>
  );
}

function PlaygroundPreviewCard({ file, png, stamp, isRendering }) {
  const pngUrl = toPlaygroundFileUrl(png, stamp);
  const codeUrl = `/api/playground/file?file=${encodeURIComponent(file)}`;
  const emptyMessage = isRendering ? 'Rendering...' : 'Render to see preview';

  return (
    <PreviewCard
      title={file}
      initialPngUrl={pngUrl}
      codeUrl={codeUrl}
      renderEmptyMessage={emptyMessage}
      renderPadding={32}
      renderMaxHeight={360}
      loading={!png && isRendering}
    />
  );
}

function toPlaygroundFileUrl(relPath, stamp) {
  if (!relPath) return null;
  const [clean, query] = String(relPath).split('?');
  let token = typeof stamp === 'number' ? stamp : undefined;
  if (!token && query) {
    const match = query.match(/(?:^|&)t=([^&]+)/);
    if (match) token = match[1];
  }
  if (!token) token = Date.now();
  return `/api/playground/file?file=${encodeURIComponent(clean)}&t=${token}`;
}
