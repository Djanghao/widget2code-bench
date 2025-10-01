import { Card, Tabs, Typography, Button, Modal, Spin, Tooltip, message } from "antd";
import { useMemo, useState, useEffect, useRef } from "react";

const { Text } = Typography;

export default function PreviewCard({ title, code, prompt, sourceUrl, run, filePath }) {
  const [compareOpen, setCompareOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pngUrl, setPngUrl] = useState(null);
  const [dimensions, setDimensions] = useState(null);
  const [origDimensions, setOrigDimensions] = useState(null);

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

  const handleOriginalLoad = (e) => {
    const img = e.target;
    setOrigDimensions({ width: img.naturalWidth, height: img.naturalHeight });
  };

  const promptText = prompt ?? "";

  return (
    <Card size="small" title={<Text strong>{title}</Text>} bodyStyle={{ padding: 12 }}>
      <Tabs
        size="small"
        tabBarExtraContent={{
          right: (
            <div style={{ display: 'flex', gap: 8 }}>
              <Tooltip title={pngUrl ? "Download PNG" : "Render first"}>
                <Button
                  size="small"
                  href={pngUrl || undefined}
                  download={`${String(title || 'render').replace(/\s+/g, '_')}.png`}
                  disabled={!pngUrl}
                >
                  Download
                </Button>
              </Tooltip>
              <Button size="small" onClick={() => setCompareOpen(true)} disabled={!sourceUrl}>
                Compare
              </Button>
            </div>
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
      <CompareModal
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
        title={title}
        sourceUrl={sourceUrl}
        renderUrl={pngUrl}
        loading={loading}
        origDimensions={origDimensions}
        renderDimensions={dimensions}
        onOriginalLoad={handleOriginalLoad}
        onRenderLoad={handleImageLoad}
      />
    </Card>
  );
}

function WidgetPreview({ pngUrl, dimensions, onLoad, maxHeight = 400, padding = 40, displaySize }) {
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
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block', padding }}>
      <img
        ref={imgRef}
        src={pngUrl}
        alt="widget"
        onLoad={handleLoad}
        style={displaySize
          ? { display: 'block', width: displaySize.width, height: displaySize.height }
          : { display: 'block', maxWidth: '100%', maxHeight: maxHeight }
        }
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

function CompareModal({
  open,
  onClose,
  title,
  sourceUrl,
  renderUrl,
  loading,
  origDimensions,
  renderDimensions,
  onOriginalLoad,
  onRenderLoad,
}) {
  const [viewport, setViewport] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const update = () => setViewport({ w: window.innerWidth, h: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  // Compute a common scale so both images have the same proportional scaling,
  // stay slightly smaller, and always fit within the viewport without scrolling.
  const padding = 40; // WidgetPreview padding
  const gap = 16; // Gap between columns
  const shrink = 0.9; // Show a little smaller, as requested
  const modalMarginX = 64; // Side margins to keep modal within viewport
  const modalMarginY = 160; // Top/bottom margins incl. header, paddings
  const bodyPaddingX = 48; // Approx. horizontal padding inside modal body
  const headerExtra = 34; // Space for "Original"/"Render" labels

  // Measurement overlay sizing (match WidgetPreview styles)
  const measureOffset = 12; // distance from PNG edge to measurement line
  const measureLabelGap = 6; // gap between line and pill label
  const pillPadX = 8; // label pill horizontal padding (each side)
  const pillBorder = 1; // label border width
  const pillFontCharW = 8; // approx width per character for 12px font
  const pillHeight = 22; // approx overall pill height

  const estimatePillWidth = (value) => {
    const textLen = String(value ?? '').length + 2; // includes 'px'
    return textLen * pillFontCharW + (2 * pillPadX) + (2 * pillBorder);
  };

  const { scale, origSize, renderSize, modalWidth, extras } = useMemo(() => {
    // Fallback width that fits within viewport while loading/no dims
    if (!origDimensions || !renderDimensions || viewport.h === 0 || viewport.w === 0) {
      const fallbackWidth = Math.max(360, viewport.w ? viewport.w - modalMarginX : 800);
      return { scale: 1, origSize: null, renderSize: null, modalWidth: fallbackWidth, extras: { rightL: 0, rightR: 0, bottom: 0 } };
    }

    const maxH = Math.max(origDimensions.height, renderDimensions.height);
    const sumW = (origDimensions.width || 0) + (renderDimensions.width || 0);

    const availableWidth = Math.max(320, viewport.w - modalMarginX);
    const availableHeight = Math.max(260, viewport.h - modalMarginY);

    // Compute extra spaces needed for measurement labels beyond base padding
    const rightExtraLeft = Math.max(0, (measureOffset + measureLabelGap + estimatePillWidth(origDimensions.height)) - padding);
    const rightExtraRight = Math.max(0, (measureOffset + measureLabelGap + estimatePillWidth(renderDimensions.height)) - padding);
    const bottomExtraCommon = Math.max(0, (measureOffset + measureLabelGap + pillHeight) - padding);

    // Height bound: ensure scaled image plus padding and label fits in height (worst-case bottom extra)
    const heightNumerator = Math.max(80, availableHeight - (2 * padding + Math.max(bottomExtraCommon, 0) + headerExtra));
    const heightBound = heightNumerator > 0 && maxH > 0 ? heightNumerator / maxH : 0.01;

    // Width bound: ensure two images + paddings + extras + gap fit into available width
    const widthNumerator = Math.max(
      160,
      availableWidth - (bodyPaddingX + (2 * padding + rightExtraLeft) + (2 * padding + rightExtraRight) + gap)
    );
    const widthBound = widthNumerator > 0 && sumW > 0 ? widthNumerator / sumW : 0.01;

    let s = Math.min(1, heightBound, widthBound) * shrink;
    if (!isFinite(s) || s <= 0) s = 0.01;

    const oW = Math.round((origDimensions.width || 0) * s);
    const oH = Math.round((origDimensions.height || 0) * s);
    const rW = Math.round((renderDimensions.width || 0) * s);
    const rH = Math.round((renderDimensions.height || 0) * s);

    const contentWidth = oW + rW + (2 * padding + rightExtraLeft) + (2 * padding + rightExtraRight) + gap;
    const finalModalWidth = Math.min(availableWidth, contentWidth + bodyPaddingX);

    return {
      scale: s,
      origSize: { width: oW, height: oH },
      renderSize: { width: rW, height: rH },
      modalWidth: Math.max(360, finalModalWidth),
      extras: { rightL: rightExtraLeft, rightR: rightExtraRight, bottom: bottomExtraCommon },
    };
  }, [origDimensions, renderDimensions, viewport.h, viewport.w]);

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={modalWidth}
      bodyStyle={{ overflow: 'hidden' }}
      destroyOnClose
      centered
      title="Compare"
    >
      <div style={{ display: 'flex', gap, flexWrap: 'nowrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '0 0 auto', paddingRight: extras.rightL, paddingBottom: extras.bottom, overflow: 'visible' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text strong>Original</Text>
            {sourceUrl ? (
              <Tooltip title="Download PNG">
                <Button
                  size="small"
                  href={sourceUrl}
                  download={`${String(title || 'original').replace(/\s+/g, '_')}.png`}
                >
                  Download
                </Button>
              </Tooltip>
            ) : null}
          </div>
          {sourceUrl ? (
            <div style={{ background: '#f5f5f5', borderRadius: 8, border: '1px solid #eef0f3', overflow: 'visible' }}>
              <WidgetPreview
                pngUrl={sourceUrl}
                dimensions={origDimensions}
                onLoad={onOriginalLoad}
                displaySize={origSize || undefined}
                padding={padding}
              />
            </div>
          ) : (
            <div className="center" style={{ height: 200 }}>No source image</div>
          )}
        </div>
        <div style={{ flex: '0 0 auto', paddingRight: extras.rightR, paddingBottom: extras.bottom, overflow: 'visible' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text strong>Render</Text>
            {renderUrl ? (
              <Tooltip title="Download PNG">
                <Button
                  size="small"
                  href={renderUrl}
                  download={`${String(title || 'render').replace(/\s+/g, '_')}.png`}
                  disabled={loading}
                >
                  Download
                </Button>
              </Tooltip>
            ) : null}
          </div>
          <div style={{ background: '#f5f5f5', borderRadius: 8, border: '1px solid #eef0f3', overflow: 'visible' }}>
            {loading ? (
              <Spin size="large" />
            ) : renderUrl ? (
              <WidgetPreview
                pngUrl={renderUrl}
                dimensions={renderDimensions}
                onLoad={onRenderLoad}
                displaySize={renderSize || undefined}
                padding={padding}
              />
            ) : (
              <Text type="secondary">Failed to render</Text>
            )}
          </div>
        </div>
      </div>
    </Modal>
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
