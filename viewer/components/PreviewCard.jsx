import { Card, Tabs, Typography, Button, Modal, Spin, Tooltip, message } from "antd";
import { useMemo, useState, useEffect } from "react";

const { Text } = Typography;

export default function PreviewCard({ title, code, prompt, sourceUrl, run, filePath }) {
  const [compareOpen, setCompareOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pngUrl, setPngUrl] = useState(null);
  const [dimensions, setDimensions] = useState(null);

  useEffect(() => {
    if (!run || !filePath) return;

    setLoading(true);
    fetch(`/api/render?run=${encodeURIComponent(run)}&file=${encodeURIComponent(filePath)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.pngPath) {
          const url = `/api/file?run=${encodeURIComponent(run)}&file=${encodeURIComponent(data.pngPath)}`;
          setPngUrl(url);
        } else if (data.error) {
          console.error('Render error:', data.error);
        }
      })
      .catch((err) => {
        console.error('Failed to render:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [run, filePath]);

  const handleImageLoad = (e) => {
    const img = e.target;
    setDimensions({ width: img.naturalWidth, height: img.naturalHeight });
  };

  const promptText = prompt ?? "";

  return (
    <Card size="small" title={<Text strong>{title}</Text>} bodyStyle={{ padding: 12 }}>
      <Tabs
        size="small"
        tabBarExtraContent={{
          right: (
            <Button size="small" onClick={() => setCompareOpen(true)} disabled={!sourceUrl}>
              Compare
            </Button>
          ),
        }}
        items={[
          {
            key: "render",
            label: "Render",
            children: (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 420, background: '#f5f5f5', borderRadius: 8 }}>
                {loading ? (
                  <Spin size="large" />
                ) : pngUrl ? (
                  <WidgetPreview pngUrl={pngUrl} dimensions={dimensions} onLoad={handleImageLoad} />
                ) : (
                  <Text type="secondary">Failed to render</Text>
                )}
              </div>
            ),
          },
          {
            key: "code",
            label: "Code",
            children: (
              <CodeViewer
                label="Code"
                content={code || ""}
                placeholder="No code available"
                copyMessage="Code copied"
              />
            ),
          },
          {
            key: "prompt",
            label: "Prompt",
            children: (
              <CodeViewer
                label="Prompt"
                content={promptText}
                placeholder="No prompt available"
                copyMessage="Prompt copied"
              />
            ),
          },
        ]}
      />
      <Modal
        open={compareOpen}
        onCancel={() => setCompareOpen(false)}
        footer={null}
        width={1000}
        destroyOnClose
        centered
        title="Compare"
      >
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 280 }}>
            <Text strong style={{ display: "block", marginBottom: 8 }}>Original</Text>
            {sourceUrl ? (
              <img
                alt="original"
                src={sourceUrl}
                style={{ width: "100%", maxHeight: "60vh", objectFit: "contain", borderRadius: 8, border: "1px solid #eef0f3" }}
              />
            ) : (
              <div className="center" style={{ height: 200 }}>No source image</div>
            )}
          </div>
          <div style={{ flex: 1, minWidth: 280 }}>
            <Text strong style={{ display: "block", marginBottom: 8 }}>Render</Text>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, background: '#f5f5f5', borderRadius: 8, border: "1px solid #eef0f3" }}>
              {loading ? (
                <Spin size="large" />
              ) : pngUrl ? (
                <img
                  alt="render"
                  src={pngUrl}
                  style={{ maxWidth: "100%", maxHeight: "60vh", objectFit: "contain" }}
                />
              ) : (
                <Text type="secondary">Failed to render</Text>
              )}
            </div>
          </div>
        </div>
      </Modal>
    </Card>
  );
}

function WidgetPreview({ pngUrl, dimensions, onLoad }) {
  return (
    <div style={{ position: 'relative', display: 'inline-block', padding: 40 }}>
      <img
        src={pngUrl}
        alt="widget"
        onLoad={onLoad}
        style={{ display: 'block', maxWidth: '100%', maxHeight: 400 }}
      />
      {dimensions && (
        <>
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 20,
              height: 1,
              background: '#ff4d4f',
              pointerEvents: 'none'
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: 0,
              bottom: 4,
              fontSize: 12,
              color: '#ff4d4f',
              fontWeight: 600,
              whiteSpace: 'nowrap'
            }}
          >
            {dimensions.width}px
          </div>
          <div
            style={{
              position: 'absolute',
              right: 20,
              top: 0,
              bottom: 0,
              width: 1,
              background: '#ff4d4f',
              pointerEvents: 'none'
            }}
          />
          <div
            style={{
              position: 'absolute',
              right: 4,
              top: 0,
              fontSize: 12,
              color: '#ff4d4f',
              fontWeight: 600,
              writingMode: 'vertical-rl',
              transform: 'rotate(180deg)'
            }}
          >
            {dimensions.height}px
          </div>
        </>
      )}
    </div>
  );
}

function CodeViewer({ label, content, placeholder, copyMessage }) {
  const normalized = useMemo(() => (content ?? "").replace(/\r\n/g, "\n"), [content]);
  const hasContent = normalized.length > 0;

  const handleCopy = async () => {
    if (!hasContent) return;
    try {
      if (typeof navigator === "undefined" || !navigator.clipboard) {
        message.warning("Clipboard unavailable");
        return;
      }
      await navigator.clipboard.writeText(normalized);
      message.success(copyMessage || "Copied");
    } catch (err) {
      console.error("copy failed", err);
      message.error("Copy failed");
    }
  };

  return (
    <div className="codeEditor">
      <div className="codeEditorToolbar">
        <div className="codeEditorDots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
        <Tooltip title={hasContent ? "Copy" : "Nothing to copy"}>
          <Button size="small" type="text" onClick={handleCopy} disabled={!hasContent}>
            Copy
          </Button>
        </Tooltip>
      </div>
      <div className="codeEditorBody">
        <pre className={`codeEditorContent${hasContent ? "" : " codeEditorEmpty"}`}>
          {hasContent ? normalized : placeholder || ""}
        </pre>
      </div>
    </div>
  );
}
