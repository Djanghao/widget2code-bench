import { Card, Tabs, Typography, Button, Modal, Spin, Tooltip, message } from "antd";
import { useMemo, useState, useEffect, useRef } from "react";

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
  const containerRef = useRef(null);
  const imgRef = useRef(null);

  const [imgBox, setImgBox] = useState(null);

  useEffect(() => {
    function updateBox() {
      if (!containerRef.current || !imgRef.current) return;
      const c = containerRef.current.getBoundingClientRect();
      const r = imgRef.current.getBoundingClientRect();
      setImgBox({
        left: r.left - c.left,
        top: r.top - c.top,
        width: r.width,
        height: r.height,
      });
    }

    updateBox();
    const ro = new (window.ResizeObserver || class { observe(){} disconnect(){} })((entries) => {
      updateBox();
    });
    if (containerRef.current) ro.observe(containerRef.current);
    if (imgRef.current) ro.observe(imgRef.current);
    window.addEventListener('resize', updateBox);

    return () => {
      window.removeEventListener('resize', updateBox);
      ro.disconnect && ro.disconnect();
    };
  }, [pngUrl]);

  const handleLoad = (e) => {
    onLoad && onLoad(e);
    // Ensure we measure after image has its layout
    requestAnimationFrame(() => {
      if (!containerRef.current || !imgRef.current) return;
      const c = containerRef.current.getBoundingClientRect();
      const r = imgRef.current.getBoundingClientRect();
      setImgBox({ left: r.left - c.left, top: r.top - c.top, width: r.width, height: r.height });
    });
  };

  const color = '#1677ff';
  const line = 2; // line thickness
  const offset = 12; // gap between PNG edge and measurement line
  const labelGap = 6; // gap between line and pill label

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block', padding: 40 }}>
      <img
        ref={imgRef}
        src={pngUrl}
        alt="widget"
        onLoad={handleLoad}
        style={{ display: 'block', maxWidth: '100%', maxHeight: 400 }}
      />
      {dimensions && imgBox && (
        <>
          {/* Horizontal measurement line below the image, aligned to PNG edges */}
          <div
            style={{
              position: 'absolute',
              left: imgBox.left,
              top: imgBox.top + imgBox.height + offset,
              width: imgBox.width,
              height: line,
              background: color,
              borderRadius: line,
              pointerEvents: 'none'
            }}
          />
          {/* Horizontal end caps */}
          <div
            style={{
              position: 'absolute',
              left: imgBox.left - (line - 1),
              top: imgBox.top + imgBox.height + offset - 3,
              width: line,
              height: 8,
              background: color,
              borderRadius: line,
              pointerEvents: 'none'
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: imgBox.left + imgBox.width - 1,
              top: imgBox.top + imgBox.height + offset - 3,
              width: line,
              height: 8,
              background: color,
              borderRadius: line,
              pointerEvents: 'none'
            }}
          />
          {/* Horizontal pill label (outside, not on PNG side) */}
          <div
            style={{
              position: 'absolute',
              left: imgBox.left + imgBox.width / 2,
              top: imgBox.top + imgBox.height + offset + labelGap,
              transform: 'translateX(-50%)',
              background: '#fff',
              color,
              border: '1px solid #d0d7de',
              borderRadius: 9999,
              padding: '2px 8px',
              fontSize: 12,
              fontWeight: 600,
              lineHeight: 1.2,
              boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              whiteSpace: 'nowrap',
              pointerEvents: 'none'
            }}
          >
            {dimensions.width}px
          </div>

          {/* Vertical measurement line to the right of the image, aligned to PNG edges */}
          <div
            style={{
              position: 'absolute',
              left: imgBox.left + imgBox.width + offset,
              top: imgBox.top,
              width: line,
              height: imgBox.height,
              background: color,
              borderRadius: line,
              pointerEvents: 'none'
            }}
          />
          {/* Vertical end caps */}
          <div
            style={{
              position: 'absolute',
              left: imgBox.left + imgBox.width + offset - 3,
              top: imgBox.top - (line - 1),
              width: 8,
              height: line,
              background: color,
              borderRadius: line,
              pointerEvents: 'none'
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: imgBox.left + imgBox.width + offset - 3,
              top: imgBox.top + imgBox.height - 1,
              width: 8,
              height: line,
              background: color,
              borderRadius: line,
              pointerEvents: 'none'
            }}
          />
          {/* Vertical pill label (outside, not on PNG side) */}
          <div
            style={{
              position: 'absolute',
              left: imgBox.left + imgBox.width + offset + labelGap,
              top: imgBox.top + imgBox.height / 2,
              transform: 'translateY(-50%)',
              background: '#fff',
              color,
              border: '1px solid #d0d7de',
              borderRadius: 9999,
              padding: '2px 8px',
              fontSize: 12,
              fontWeight: 600,
              lineHeight: 1.2,
              boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              whiteSpace: 'nowrap',
              pointerEvents: 'none'
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
