import { useEffect, useMemo, useState } from "react";
import { Layout, Typography, Input, List, Avatar, Empty, Spin, Flex, Divider, Modal, Button, Segmented } from "antd";
import { MenuFoldOutlined, MenuUnfoldOutlined, EyeOutlined, ExperimentOutlined } from "@ant-design/icons";
import Link from "next/link";
import RunPicker from "../components/RunPicker";
import PreviewCard from "../components/PreviewCard";

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

export default function Home() {
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
  const [renderStatus, setRenderStatus] = useState('idle'); // idle | checking | rendering | ready

  useEffect(() => {
    fetch("/api/runs").then((r) => r.json()).then((d) => {
      setRuns(d.runs || []);
      if (d.runs && d.runs.length > 0) setRun(d.runs[0].name);
    });
  }, []);

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
  }, [run]);

  useEffect(() => {
    if (!run || !selected) return;
    setLoadingResults(true);
    fetch(`/api/results?run=${encodeURIComponent(run)}&image=${encodeURIComponent(selected)}`)
      .then((r) => r.json())
      .then((d) => setResults(d.categories || {}))
      .finally(() => setLoadingResults(false));

    // Check PNG completeness first; if incomplete, trigger batch render and wait
    const doCheckAndMaybeRender = async () => {
      try {
        setRenderStatus('checking');
        const checkRes = await fetch(`/api/check-pngs?run=${encodeURIComponent(run)}&image=${encodeURIComponent(selected)}`);
        const check = await checkRes.json();
        if (check && check.complete) {
          console.log(`[viewer] PNG completeness: complete (total=${check.total})`);
          setRenderStatus('ready');
          return;
        } else {
          console.log(`[viewer] PNG completeness: incomplete (missing=${check?.missingCount ?? 'unknown'}). Starting batch render...`);
        }

        setRenderStatus('rendering');
        await fetch('/api/batch-render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run, image: selected })
        });

        // After batch render completes, verify PNGs exist; poll a bit in case of FS lag
        for (let i = 0; i < 20; i++) { // up to ~10s
          const r = await fetch(`/api/check-pngs?run=${encodeURIComponent(run)}&image=${encodeURIComponent(selected)}`);
          const d = await r.json();
          if (d && d.complete) {
            console.log('[viewer] Batch render complete. PNGs ready.');
            setRenderStatus('ready');
            return;
          }
          await new Promise((res) => setTimeout(res, 500));
        }
        console.log('[viewer] PNGs not fully ready after waiting; proceeding anyway.');
        setRenderStatus('ready');
      } catch (err) {
        console.error('Render readiness check failed:', err);
        setRenderStatus('ready');
      }
    };
    doCheckAndMaybeRender();
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

  return (
    <Layout className="layout">
      <Header style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 24px" }}>
        <Title level={4} style={{ color: "#0f1419", margin: 0, fontWeight: 700 }}>Widget2Code</Title>
        <div style={{ display: "flex", gap: 8, marginLeft: 16 }}>
          <Link href="/" passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="primary" icon={<EyeOutlined />}>
                Viewer
              </Button>
            </a>
          </Link>
          <Link href="/playground" passHref legacyBehavior>
            <a style={{ textDecoration: 'none' }}>
              <Button type="default" icon={<ExperimentOutlined />}>
                Playground
              </Button>
            </a>
          </Link>
        </div>
        <div style={{ flex: 1 }} />
        <RunPicker runs={runs} value={run} onChange={setRun} />
      </Header>
      <Layout style={{ height: "calc(100vh - 64px)", position: "relative" }}>
        {siderCollapsed ? (
          <Button
            className="siderFloatToggle"
            type="default"
            shape="circle"
            size="small"
            icon={<MenuUnfoldOutlined />}
            onClick={() => setSiderCollapsed(false)}
            aria-label="Expand sidebar"
            style={{ position: "absolute", left: 12, top: 12, zIndex: 20 }}
          />
        ) : null}
        <Sider
          width={320}
          collapsedWidth={0}
          collapsible
          collapsed={siderCollapsed}
          trigger={null}
          className={`appSider${siderCollapsed ? " appSiderCollapsed" : ""}`}
        >
          {siderCollapsed ? (
            <div className="siderHeader">
              <Button
                type="text"
                icon={<MenuUnfoldOutlined />}
                onClick={() => setSiderCollapsed(false)}
                aria-label="Expand sidebar"
              />
            </div>
          ) : (
            <div className="siderHeader" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button
                type="text"
                icon={<MenuFoldOutlined />}
                onClick={() => setSiderCollapsed(true)}
                aria-label="Collapse sidebar"
              />
              <Input.Search
                placeholder="Filter images"
                allowClear
                onChange={(e) => setFilter(e.target.value)}
                value={filter}
              />
            </div>
          )}
          <div className="siderScroll">
            {loadingImages ? (
              <div className="center" style={{ height: 200 }}><Spin /></div>
            ) : filtered.length ? (
              <List
                dataSource={filtered}
                renderItem={(item) => (
                  <List.Item
                    onClick={() => setSelected(item.id)}
                    style={{ cursor: "pointer", background: selected === item.id ? "#f0f7ff" : undefined, borderRadius: 8, margin: 4, padding: 8 }}
                  >
                    <List.Item.Meta
                      avatar={
                        item.source ? (
                          <Avatar shape="square" size={48} src={`/api/file?run=${encodeURIComponent(run)}&file=${encodeURIComponent(item.source)}`} />
                        ) : (
                          <Avatar shape="square" size={48}>?</Avatar>
                        )
                      }
                      title={<Text>{item.id}</Text>}
                      description={item.source ? <Text type="secondary" style={{ fontSize: 12 }}>{item.source.split("/").pop()}</Text> : null}
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="No images" style={{ marginTop: 48 }} />
            )}
          </div>
        </Sider>
        <Content style={{ padding: 16, overflow: "auto" }}>
          {!selected ? (
            <Empty description="Select an image" />
          ) : loadingResults ? (
            <div className="center" style={{ height: 240 }}><Spin /></div>
          ) : renderStatus !== 'ready' ? (
            <div className="center" style={{ height: 240 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Spin />
                <Text type="secondary">
                  {renderStatus === 'checking' ? 'Checking PNGs...' : 'Rendering PNGs...'}
                </Text>
              </div>
            </div>
          ) : (
            <div>
              <Flex align="center" gap={12} wrap="wrap" style={{ marginBottom: 8 }}>
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
                          code={it.code}
                          prompt={it.prompt}
                          sourceUrl={selectedSource}
                          run={run}
                          filePath={it.path}
                        />
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </Content>
      </Layout>
      <Modal
        open={sourceModalOpen}
        onCancel={() => setSourceModalOpen(false)}
        footer={null}
        width={900}
        destroyOnClose
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
    </Layout>
  );
}
