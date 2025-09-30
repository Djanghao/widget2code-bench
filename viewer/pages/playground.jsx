import { useEffect, useMemo, useRef, useState } from 'react';
import { Layout, Typography, Button, Divider, Upload, message, Input, Radio, List, Empty, Spin, Space, Card, Tooltip, Segmented, Tabs } from 'antd';
import { InboxOutlined, FolderOpenOutlined, UploadOutlined, DeleteOutlined, DownloadOutlined, PlayCircleOutlined, PlusOutlined, EyeOutlined, ExperimentOutlined, ThunderboltOutlined, CloudUploadOutlined } from '@ant-design/icons';
import Link from 'next/link';

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;
const { Dragger } = Upload;

export default function Playground() {
  const [mode, setMode] = useState('upload'); // 'upload' | 'live'
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
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
    setLoading(true);
    try {
      const r = await fetch('/api/playground/list');
      const d = await r.json();
      setFiles(d.items || []);
    } catch (err) {
      console.error('list failed', err);
    } finally {
      setLoading(false);
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
    showUploadList: true,
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

  return (
    <Layout className="layout">
      <Header style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 24px' }}>
        <Title level={4} style={{ color: '#0f1419', margin: 0, fontWeight: 700 }}>Widget2Code</Title>
        <div style={{ display: 'flex', gap: 8, marginLeft: 16 }}>
          <Link href="/" passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="default" icon={<EyeOutlined />}>
                Viewer
              </Button>
            </a>
          </Link>
          <Link href="/playground" passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="primary" icon={<ExperimentOutlined />}>
                Playground
              </Button>
            </a>
          </Link>
        </div>
        <Segmented
          value={mode}
          onChange={setMode}
          options={[
            { label: 'Upload', value: 'upload', icon: <CloudUploadOutlined /> },
            { label: 'Live Paste', value: 'live', icon: <ThunderboltOutlined /> }
          ]}
          style={{ marginLeft: 24 }}
        />
        <div style={{ flex: 1 }} />
        {mode === 'upload' && (
          <Space>
            <Button icon={<DeleteOutlined />} onClick={async () => { await fetch('/api/playground/reset', { method: 'POST' }); await refreshList(); }}>Clear</Button>
            <Button type="primary" icon={<PlayCircleOutlined />} loading={rendering} disabled={!files.length || !anyRenderable} onClick={onRenderAll}>Render All</Button>
          </Space>
        )}
      </Header>
      <Layout style={{ height: 'calc(100vh - 64px)' }}>

        {mode === 'upload' ? (
          <>
            <Sider width={360} className="appSider">
              <div className="siderHeader">
                <Title level={5} style={{ margin: 0 }}>Add Files</Title>
              </div>
              <div className="siderScroll" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Dragger {...uploadProps} style={{ borderRadius: 10 }}>
                  <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p className="ant-upload-text">Click or drag files/folder to upload</p>
                  <p className="ant-upload-hint">HTML, JSX, and any assets; folder structure preserved</p>
                </Dragger>

                <Divider style={{ margin: '8px 0' }} />
                <Title level={5} style={{ margin: '4px 0 8px' }}>Uploaded Files</Title>
                {loading ? (
                  <div className="center" style={{ height: 120 }}><Spin /></div>
                ) : files.length ? (
                  <List
                    size="small"
                    dataSource={files}
                    renderItem={(item) => (
                      <List.Item>
                        <List.Item.Meta
                          title={<Text>{item.file}</Text>}
                          description={item.png ? <Text type="secondary">Rendered</Text> : <Text type="secondary">Pending</Text>}
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="No files yet" />
                )}
              </div>
            </Sider>
            <Content style={{ padding: 16, overflow: 'auto' }}>
              <Space align="center" style={{ marginBottom: 8 }}>
                <Title level={5} style={{ margin: 0 }}>Previews</Title>
                {rendering ? <Spin size="small" /> : null}
              </Space>
              {!files.length ? (
                <Empty description="Upload or paste code to begin" style={{ marginTop: 48 }} />
              ) : (
                <div className="grid">
                  {files.map((f) => (
                    <PreviewBox key={f.file} file={f.file} png={f.png} />
                  ))}
                </div>
              )}
            </Content>
          </>
        ) : (
          <div style={{ display: 'flex', height: 'calc(100vh - 140px)' }}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid #eef0f3' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #eef0f3', background: '#fafafa' }}>
                <Space>
                  <Text strong>Code Editor</Text>
                  <Radio.Group value={liveType} onChange={(e) => setLiveType(e.target.value)} size="small">
                    <Radio.Button value="html">HTML</Radio.Button>
                    <Radio.Button value="jsx">JSX</Radio.Button>
                  </Radio.Group>
                </Space>
              </div>
              <Input.TextArea
                value={liveCode}
                onChange={(e) => setLiveCode(e.target.value)}
                placeholder={`Paste your ${liveType.toUpperCase()} code here...\n\nIt will auto-render as you type!`}
                style={{ flex: 1, resize: 'none', border: 'none', borderRadius: 0, fontFamily: 'monospace', fontSize: 14 }}
              />
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #eef0f3', background: '#fafafa', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong>Live Preview</Text>
                {liveRendering && <Spin size="small" />}
              </div>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5', overflow: 'auto', padding: 16 }}>
                {livePng ? (
                  <img
                    key={livePng}
                    alt="live preview"
                    src={`/api/playground/file?file=${encodeURIComponent(livePng.split('?')[0])}&t=${livePng.split('?t=')[1] || Date.now()}`}
                    style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  />
                ) : liveCode.trim() ? (
                  liveRendering ? <Spin tip="Rendering..." /> : <Empty description="Render failed" />
                ) : (
                  <Empty description="Start typing to see live preview" />
                )}
              </div>
            </div>
          </div>
        )}
      </Layout>
    </Layout>
  );
}

function PreviewBox({ file, png }) {
  const [loading, setLoading] = useState(false);
  const [pngPath, setPngPath] = useState(png || null);

  useEffect(() => { setPngPath(png || null); }, [png]);

  const doRender = async () => {
    setLoading(true);
    try {
      const r = await fetch(`/api/playground/render-one?file=${encodeURIComponent(file)}`);
      const d = await r.json();
      if (r.ok && d.png) setPngPath(d.png);
      else throw new Error(d?.error || 'render failed');
    } catch (err) {
      message.error('Render failed');
    } finally {
      setLoading(false);
    }
  };

  const downloadHref = pngPath ? `/api/playground/file?file=${encodeURIComponent(pngPath)}` : undefined;

  return (
    <Card
      size="small"
      title={<Text strong style={{ wordBreak: 'break-all' }}>{file}</Text>}
      extra={<Space>
        <Tooltip title="Render">
          <Button size="small" icon={<PlayCircleOutlined />} onClick={doRender} loading={loading} />
        </Tooltip>
        <Tooltip title={pngPath ? 'Download PNG' : 'Render first'}>
          <Button size="small" icon={<DownloadOutlined />} disabled={!pngPath} href={downloadHref} download={file.replace(/\.(html|jsx|js)$/i, '.png')} />
        </Tooltip>
      </Space>}
      bodyStyle={{ padding: 12 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 220, background: '#f5f5f5', borderRadius: 8 }}>
        {pngPath ? (
          <img alt={file} src={`/api/playground/file?file=${encodeURIComponent(pngPath)}`} style={{ maxWidth: '100%', maxHeight: 260 }} />
        ) : loading ? (
          <Spin />
        ) : (
          <Text type="secondary">No PNG yet</Text>
        )}
      </div>
    </Card>
  );
}

