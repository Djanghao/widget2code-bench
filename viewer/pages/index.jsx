import { useEffect, useMemo, useState } from "react";
import { Layout, Typography, Input, List, Avatar, Empty, Spin, Flex, Divider } from "antd";
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
  }, [run, selected]);

  const filtered = useMemo(() => {
    if (!filter) return images;
    const f = filter.toLowerCase();
    return images.filter((i) => i.id.toLowerCase().includes(f));
  }, [images, filter]);

  return (
    <Layout className="layout">
      <Header style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Title level={4} style={{ color: "#fff", margin: 0 }}>Widget2Code Viewer</Title>
        <div style={{ flex: 1 }} />
        <RunPicker runs={runs} value={run} onChange={setRun} />
      </Header>
      <Layout>
        <Sider width={320} style={{ background: "#fff", borderRight: "1px solid #eef0f3" }}>
          <div style={{ padding: 12 }}>
            <Input.Search placeholder="Filter images" allowClear onChange={(e) => setFilter(e.target.value)} />
          </div>
          <div style={{ height: "calc(100vh - 112px)", overflow: "auto", paddingInline: 8 }}>
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
        <Content style={{ padding: 16 }}>
          {!selected ? (
            <Empty description="Select an image" />
          ) : loadingResults ? (
            <div className="center" style={{ height: 240 }}><Spin /></div>
          ) : (
            <div>
              <Flex align="center" gap={12} wrap="wrap" style={{ marginBottom: 8 }}>
                <Title level={5} style={{ margin: 0 }}>{selected}</Title>
                {(() => {
                  const src = images.find((i) => i.id === selected)?.source;
                  return src ? (
                    <img
                      alt="source"
                      src={`/api/file?run=${encodeURIComponent(run)}&file=${encodeURIComponent(src)}`}
                      style={{ height: 64, borderRadius: 8, border: "1px solid #eef0f3", background: "#fff" }}
                    />
                  ) : null;
                })()}
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
                        <PreviewCard key={it.name} title={it.name} ext={it.ext} code={it.code} />
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </Content>
      </Layout>
    </Layout>
  );
}

