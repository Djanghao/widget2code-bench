import { useEffect, useMemo, useState } from "react";
import { Layout, Typography, Input, Empty, Spin, Flex, Divider, Modal, Button, message, Progress } from "antd";
import { MenuFoldOutlined, MenuUnfoldOutlined, EyeOutlined, ExperimentOutlined, ThunderboltOutlined, DownloadOutlined, CheckCircleOutlined, StopOutlined } from "@ant-design/icons";
import Link from "next/link";
import { useRouter } from "next/router";
import RunPicker from "../components/RunPicker";
import PreviewCard from "../components/PreviewCard";
import CheckRunModal from "../components/CheckRunModal";

const { Sider } = Layout;
const { Title, Text } = Typography;

export default function Home() {
  const router = useRouter();
  const [runs, setRuns] = useState([]);
  const [run, setRun] = useState(null);
  const [images, setImages] = useState([]);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [loadingImages, setLoadingImages] = useState(false);
  const [loadingResults, setLoadingResults] = useState(false);
  const [results, setResults] = useState({});
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [siderCollapsed, setSiderCollapsed] = useState(false);
  const [renderStatus, setRenderStatus] = useState('idle');
  const [renderingAll, setRenderingAll] = useState(false);
  const [checkModalOpen, setCheckModalOpen] = useState(false);
  const [checkData, setCheckData] = useState(null);
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkError, setCheckError] = useState(null);
  const [renderProgress, setRenderProgress] = useState({ total: 0, completed: 0, isRendering: false });

  useEffect(() => {
    fetch("/api/runs").then((r) => r.json()).then((d) => {
      setRuns(d.runs || []);
      const runFromUrl = router.query.run;
      if (runFromUrl && d.runs && d.runs.some(r => r.name === runFromUrl)) {
        setRun(runFromUrl);
      } else if (d.runs && d.runs.length > 0) {
        setRun(d.runs[0].name);
      }
    });
  }, [router.query.run]);

  useEffect(() => {
    if (!run) return;
    setLoadingImages(true);
    fetch(`/api/images?run=${encodeURIComponent(run)}`)
      .then((r) => r.json())
      .then((d) => {
        const list = (d.images || []).sort((a, b) => (a.id > b.id ? 1 : -1));
        setImages(list);
        setSelected(list.length ? list[0].id : null);
      })
      .finally(() => setLoadingImages(false));

    const checkIfRendering = async () => {
      try {
        const statusResponse = await fetch(`/api/render-status?run=${encodeURIComponent(run)}`);
        const statusData = await statusResponse.json();

        if (statusData.isRendering) {
          const pngResponse = await fetch(`/api/check-run-pngs?run=${encodeURIComponent(run)}`);
          const pngData = await pngResponse.json();

          const completed = pngData.total - (pngData.missingCount || 0);
          setRenderProgress({
            total: pngData.total,
            completed: completed,
            isRendering: true
          });
        }
      } catch (err) {
        console.error('Check rendering status failed:', err);
      }
    };

    checkIfRendering();
  }, [run]);

  useEffect(() => {
    if (!run || !selected) return;
    setLoadingResults(true);
    fetch(`/api/results?run=${encodeURIComponent(run)}&image=${encodeURIComponent(selected)}`)
      .then((r) => r.json())
      .then((d) => setResults(d.categories || {}))
      .finally(() => setLoadingResults(false));

    const triggerBackgroundRender = async () => {
      try {
        const checkRes = await fetch(`/api/check-pngs?run=${encodeURIComponent(run)}&image=${encodeURIComponent(selected)}`);
        const check = await checkRes.json();
        if (check && check.complete) {
          console.log(`[viewer] PNG completeness: complete (total=${check.total})`);
          setRenderStatus('ready');
        } else {
          console.log(`[viewer] PNG completeness: incomplete (missing=${check?.missingCount ?? 'unknown'}). Starting background render...`);
          setRenderStatus('rendering');
          fetch('/api/batch-render', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run, image: selected })
          }).catch(err => console.error('Background render failed:', err));
        }
      } catch (err) {
        console.error('PNG check failed:', err);
        setRenderStatus('ready');
      }
    };
    triggerBackgroundRender();
  }, [run, selected]);

  const filtered = useMemo(() => {
    if (!filter) return images;
    const f = filter.toLowerCase();
    return images.filter((i) => i.id.toLowerCase().includes(f));
  }, [images, filter]);

  const selectedItem = useMemo(() => images.find((i) => i.id === selected), [images, selected]);
  const selectedSource = useMemo(() => {
    if (!run || !selectedItem || !selectedItem.source) return null;
    return `/api/file?run=${encodeURIComponent(run)}&file=${encodeURIComponent(selectedItem.source)}`;
  }, [run, selectedItem]);

  useEffect(() => {
    if (!run || !renderProgress.isRendering) return;

    const checkProgress = async () => {
      try {
        const response = await fetch(`/api/check-run-pngs?run=${encodeURIComponent(run)}`);
        const data = await response.json();

        const completed = data.total - (data.missingCount || 0);
        setRenderProgress(prev => ({
          ...prev,
          total: data.total,
          completed: completed
        }));

        if (data.complete) {
          setRenderProgress(prev => ({ ...prev, isRendering: false }));
          message.success(`All PNGs rendered! (${data.total} files)`);
        }
      } catch (err) {
        console.error('Progress check failed:', err);
      }
    };

    checkProgress();
    const interval = setInterval(checkProgress, 2000);

    return () => clearInterval(interval);
  }, [run, renderProgress.isRendering]);

  const handleRenderAll = async () => {
    if (!run) {
      message.warning('No run selected');
      return;
    }

    try {
      const checkResponse = await fetch(`/api/check-run-pngs?run=${encodeURIComponent(run)}`);
      const checkData = await checkResponse.json();

      if (checkData.complete) {
        message.success(`All PNGs already rendered (${checkData.total} files)`);
        return;
      }

      setRenderProgress({
        total: checkData.total,
        completed: checkData.total - checkData.missingCount,
        isRendering: true
      });

      const response = await fetch('/api/batch-render-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run })
      });
      const data = await response.json();
      if (!response.ok) {
        message.error(data.error || 'Failed to start batch rendering');
        setRenderProgress(prev => ({ ...prev, isRendering: false }));
      }
    } catch (err) {
      console.error('Batch render all failed:', err);
      message.error('Failed to start batch rendering');
      setRenderProgress(prev => ({ ...prev, isRendering: false }));
    }
  };

  const handleStopRender = async () => {
    if (!run) return;

    try {
      const response = await fetch('/api/stop-render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run })
      });
      const data = await response.json();

      if (data.success) {
        message.success('Render stopped');
        setRenderProgress(prev => ({ ...prev, isRendering: false }));
      } else {
        message.warning('No active render to stop');
      }
    } catch (err) {
      console.error('Stop render failed:', err);
      message.error('Failed to stop render');
    }
  };

  const handleDownloadAll = async () => {
    if (!run) {
      message.warning('No run selected');
      return;
    }

    try {
      const checkResponse = await fetch(`/api/check-run-pngs?run=${encodeURIComponent(run)}`);
      const checkData = await checkResponse.json();

      if (!checkData.complete) {
        message.warning(`Cannot download: ${checkData.missingCount} PNGs not rendered yet. Please run "Render All" first.`);
        return;
      }

      const url = `/api/download-all?run=${encodeURIComponent(run)}`;
      window.location.href = url;
      message.success('Preparing download...');
    } catch (err) {
      console.error('Download all check failed:', err);
      message.error('Failed to check PNG status');
    }
  };

  const handleCheckRun = async () => {
    if (!run) {
      message.warning('No run selected');
      return;
    }
    setCheckModalOpen(true);
    setCheckLoading(true);
    setCheckError(null);
    setCheckData(null);
    try {
      const response = await fetch(`/api/check-run?run=${encodeURIComponent(run)}`);
      const data = await response.json();
      if (response.ok) {
        setCheckData(data);
      } else {
        setCheckError(data.error || 'Failed to check run');
      }
    } catch (err) {
      console.error('Check run failed:', err);
      setCheckError('Failed to check run');
    } finally {
      setCheckLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <header style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "0 24px",
        height: 64,
        borderBottom: "1px solid #112a45",
        background: "#001529",
        flexShrink: 0,
        lineHeight: "normal"
      }}>
        <Button
          type="text"
          icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setSiderCollapsed((v) => !v)}
          aria-label={siderCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{ color: "#fff" }}
        />
        <Title level={4} style={{ color: "#fff", margin: 0, fontWeight: 700 }}>Widget2Code</Title>
        <div style={{ display: "flex", gap: 8, marginLeft: 16 }}>
          <Link href="/" prefetch passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="primary" icon={<EyeOutlined />} style={{ background: "#1677ff", borderColor: "#1677ff" }}>
                Viewer
              </Button>
            </a>
          </Link>
          <Link href="/playground" prefetch passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button icon={<ExperimentOutlined />} style={{ background: "#434343", borderColor: "#434343", color: "#fff" }}>
                Playground
              </Button>
            </a>
          </Link>
        </div>
        <div style={{ flex: 1 }} />
        <RunPicker
          runs={runs}
          value={run}
          onChange={(v) => {
            setLoadingImages(true);
            setImages([]);
            setSelected(null);
            setRun(v);
            router.push(`/?run=${encodeURIComponent(v)}`, undefined, { shallow: true });
          }}
        />
      </header>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <Sider
          width={320}
          collapsedWidth={0}
          collapsible
          collapsed={siderCollapsed}
          trigger={null}
          className="appSider"
          style={{
            background: "#fff",
            borderRight: "1px solid #e8e8e8",
            boxShadow: "2px 0 8px rgba(0,0,0,0.05)"
          }}
        >
          <div style={{
            padding: "16px 16px 12px",
            flexShrink: 0
          }}>
            <Input
              placeholder="Search images..."
              allowClear
              onChange={(e) => setFilter(e.target.value)}
              value={filter}
              size="large"
              style={{ borderRadius: 8 }}
            />
          </div>

          <div style={{
            flex: 1,
            overflow: "auto",
            padding: "0 12px 12px"
          }}>
            {loadingImages ? (
              <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 200 }}>
                <Spin />
              </div>
            ) : filtered.length ? (
              filtered.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setSelected(item.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: 12,
                    marginBottom: 8,
                    cursor: "pointer",
                    background: selected === item.id ? "#f0f7ff" : "#fafafa",
                    border: selected === item.id ? "2px solid #1677ff" : "2px solid transparent",
                    borderRadius: 12,
                    transition: "all 0.2s",
                    boxShadow: selected === item.id ? "0 2px 8px rgba(22,119,255,0.15)" : "none"
                  }}
                  onMouseEnter={(e) => {
                    if (selected !== item.id) {
                      e.currentTarget.style.background = "#f5f5f5";
                      e.currentTarget.style.transform = "translateX(2px)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selected !== item.id) {
                      e.currentTarget.style.background = "#fafafa";
                      e.currentTarget.style.transform = "translateX(0)";
                    }
                  }}
                >
                  <div style={{
                    width: 56,
                    height: 56,
                    flexShrink: 0,
                    borderRadius: 8,
                    overflow: "hidden",
                    background: "#fff",
                    border: "1px solid #e8e8e8",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center"
                  }}>
                    {item.source ? (
                      <img
                        loading="lazy"
                        src={`/api/thumbnail?run=${encodeURIComponent(run)}&file=${encodeURIComponent(item.source)}`}
                        alt={item.id}
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    ) : (
                      <Text type="secondary" style={{ fontSize: 18, fontWeight: 500 }}>?</Text>
                    )}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontWeight: 500,
                      fontSize: 14,
                      color: selected === item.id ? "#1677ff" : "#262626",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      marginBottom: 4
                    }}>
                      {item.id}
                    </div>
                    {item.source && (
                      <Text type="secondary" style={{
                        fontSize: 12,
                        display: "block",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap"
                      }}>
                        {item.source.split("/").pop()}
                      </Text>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <Empty description="No images" style={{ marginTop: 48 }} />
            )}
          </div>
        </Sider>

        <main style={{
          flex: 1,
          overflow: "auto",
          padding: 16,
          background: "#fff"
        }}>
          {!selected ? (
            <Empty description="Select an image" />
          ) : loadingResults ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 240 }}>
              <Spin />
            </div>
          ) : (
            <div>
              <Flex align="center" gap={12} wrap="wrap" style={{ marginBottom: 16 }}>
                <Title level={5} style={{ margin: 0 }}>{selected}</Title>
                {selectedSource ? (
                  <img
                    alt="source"
                    src={selectedSource}
                    style={{ height: 64, borderRadius: 8, border: "1px solid #eef0f3", background: "#fff", cursor: "pointer" }}
                    onClick={() => setSourceModalOpen(true)}
                  />
                ) : null}
              </Flex>

              <div style={{
                marginBottom: 16,
                display: 'flex',
                justifyContent: 'flex-end'
              }}>
                <div style={{
                  background: '#f5f5f5',
                  padding: '16px 20px',
                  borderRadius: 12,
                  border: '1px solid #e8e8e8',
                  width: renderProgress.isRendering ? '100%' : 'auto',
                  transition: 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                  display: 'flex'
                }}>
                  <Flex gap={12} align="center" wrap="wrap" style={{ width: '100%' }}>
                    {renderProgress.isRendering && (
                      <div style={{
                        flex: 1,
                        minWidth: 300,
                        marginRight: 12,
                        animation: 'slideInFromRight 0.4s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}>
                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text strong style={{ color: '#1677ff' }}>
                            <ThunderboltOutlined style={{ marginRight: 8 }} />
                            Rendering PNGs...
                          </Text>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <Text type="secondary">
                              {renderProgress.completed} / {renderProgress.total}
                            </Text>
                            <Button
                              danger
                              size="small"
                              icon={<StopOutlined />}
                              onClick={handleStopRender}
                            >
                              Stop
                            </Button>
                          </div>
                        </div>
                        <Progress
                          percent={renderProgress.total > 0 ? Math.round((renderProgress.completed / renderProgress.total) * 100) : 0}
                          status="active"
                          strokeColor={{
                            '0%': '#108ee9',
                            '100%': '#87d068',
                          }}
                        />
                      </div>
                    )}

                    <Button
                      type="primary"
                      icon={<ThunderboltOutlined />}
                      onClick={handleRenderAll}
                      disabled={!run || renderProgress.isRendering}
                      size="large"
                    >
                      Render All
                    </Button>

                    <Button
                      icon={<DownloadOutlined />}
                      onClick={handleDownloadAll}
                      disabled={!run}
                      size="large"
                    >
                      Download All
                    </Button>

                    <Button
                      icon={<CheckCircleOutlined />}
                      onClick={handleCheckRun}
                      disabled={!run}
                      size="large"
                    >
                      Check Run
                    </Button>
                  </Flex>
                </div>
              </div>

              <Divider style={{ margin: "8px 0 12px" }} />
              {Object.keys(results).length === 0 ? (
                <Empty description="No results" />
              ) : (
                Object.keys(results).sort().map((cat) => (
                  <div key={cat} style={{ marginBottom: 16 }}>
                    <div className="gridHeader">{cat}</div>
                    <div className="grid">
                      {results[cat].map((it) => (
                        <PreviewCard
                          key={it.name}
                          title={it.name}
                          codeUrl={it.codeUrl}
                          prompt={it.prompt}
                          sourceUrl={selectedSource}
                          run={run}
                          filePath={it.path}
                          renderStatus={renderStatus}
                          showCompare={true}
                        />
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </main>
      </div>

      <Modal
        open={sourceModalOpen}
        onCancel={() => setSourceModalOpen(false)}
        footer={null}
        width={900}
        centered
      >
        {selectedSource ? (
          <img
            alt="source"
            src={selectedSource}
            style={{ width: "100%", maxHeight: "70vh", objectFit: "contain", borderRadius: 8 }}
          />
        ) : null}
      </Modal>

      <CheckRunModal
        open={checkModalOpen}
        onClose={() => setCheckModalOpen(false)}
        run={run}
        data={checkData}
        loading={checkLoading}
        error={checkError}
      />
    </div>
  );
}
