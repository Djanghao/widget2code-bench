import { Card, Tabs, Typography, Button, Modal, Spin, Tooltip, message } from "antd";
import { useMemo, useState, useEffect, useRef } from "react";

const { Text } = Typography;

export default function PreviewCard({
  title,
  code,
  codeUrl,
  sourceUrl,
  run,
  filePath,
  initialPngUrl,
  loading: externalLoading = false,
  showCompare = false,
  renderPadding = 40,
  renderMaxHeight = 420,
  variant = 'default',
  renderEmptyMessage = 'No render available',
  codePlaceholder = 'No code available',
  cardStyle,
  cardHeight = 600,
  showCodeTab = true,
}) {
  const [compareOpen, setCompareOpen] = useState(false);
  const [loading, setLoading] = useState(Boolean(run && filePath));
  const [pngUrl, setPngUrl] = useState(initialPngUrl || null);
  const [dimensions, setDimensions] = useState(null);
  const [origDimensions, setOrigDimensions] = useState(null);
  const [resolvedCode, setResolvedCode] = useState(code || "");
  const [codeLoading, setCodeLoading] = useState(false);

  useEffect(() => {
    setPngUrl(initialPngUrl || null);
  }, [initialPngUrl]);

  useEffect(() => {
    setResolvedCode(code || "");
  }, [code]);

  useEffect(() => {
    if (!codeUrl || code) return;
    let cancelled = false;
    setCodeLoading(true);
    fetch(codeUrl)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`Failed to load code (${r.status})`))))
      .then((text) => {
        if (!cancelled) setResolvedCode(text || "");
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Code fetch failed:', err);
          message.error('Failed to load code');
        }
      })
      .finally(() => {
        if (!cancelled) setCodeLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [codeUrl, code]);

  useEffect(() => {
    if (!run || !filePath) return;

    setLoading(true);
    fetch(`/api/render?run=${encodeURIComponent(run)}&file=${encodeURIComponent(filePath)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.pngPath) {
          const url = `/api/file?run=${encodeURIComponent(run)}&file=${encodeURIComponent(data.pngPath)}`;
          setPngUrl(`${url}&t=${Date.now()}`);
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

  const effectiveLoading = loading || externalLoading;

  const CARD_BODY_PADDING = 12;

  const cardBaseStyle = variant === 'fill'
    ? { height: '100%', display: 'flex', flexDirection: 'column' }
    : { height: cardHeight, display: 'flex', flexDirection: 'column' };
  const cardBodyStyle = variant === 'fill'
    ? { padding: CARD_BODY_PADDING, paddingBottom: CARD_BODY_PADDING, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }
    : { padding: CARD_BODY_PADDING, paddingBottom: CARD_BODY_PADDING, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 };
  const mergedCardStyle = cardBaseStyle || cardStyle ? { ...(cardBaseStyle || {}), ...(cardStyle || {}) } : undefined;
  const CARD_HEADER_HEIGHT = 50;
  const TABS_BAR_HEIGHT = 46;
  const MEASUREMENT_OVERLAY_SPACE = 120;

  const contentHeight = variant === 'fill'
    ? undefined
    : cardHeight - CARD_HEADER_HEIGHT - TABS_BAR_HEIGHT - (CARD_BODY_PADDING * 2);
  const effectiveRenderMaxHeight = variant === 'fill'
    ? '100%'
    : contentHeight - MEASUREMENT_OVERLAY_SPACE;

  const tabsWrapperStyle = variant === 'fill'
    ? { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }
    : { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'visible' };
  const renderContentWrapperStyle = variant === 'fill'
    ? { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }
    : { height: contentHeight, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'visible' };
  const renderAreaStyle = variant === 'fill'
    ? {
        flex: 1,
        minHeight: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
        borderRadius: 8,
      }
    : {
        flex: 1,
        minHeight: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
        borderRadius: 8,
        overflow: 'visible',
      };
  const previewMaxHeight = effectiveRenderMaxHeight;

  const actions = [];
  actions.push(
    <Tooltip key="download" title={pngUrl ? "Download PNG" : "Render first"}>
      <Button
        size="small"
        href={pngUrl || undefined}
        download={`${String(title || 'render').replace(/\s+/g, '_')}.png`}
        disabled={!pngUrl}
      >
        Download
      </Button>
    </Tooltip>
  );

  if (showCompare) {
    actions.push(
      <Button key="compare" size="small" onClick={() => setCompareOpen(true)} disabled={!sourceUrl}>
        Compare
      </Button>
    );
  }

  return (
    <Card
      size="small"
      title={<Text strong>{title}</Text>}
      style={mergedCardStyle}
      bodyStyle={cardBodyStyle}
    >
      <div style={tabsWrapperStyle}>
        <Tabs
          size="small"
          tabBarExtraContent={actions.length ? { right: (<div style={{ display: 'flex', gap: 8 }}>{actions}</div>) } : undefined}
          items={[
            {
              key: 'render',
              label: 'Render',
              children: (
                <div style={renderContentWrapperStyle}>
                  <div style={renderAreaStyle}>
                    {effectiveLoading ? (
                      <Spin size="large" />
                    ) : pngUrl ? (
                      <WidgetPreview
                        pngUrl={pngUrl}
                        dimensions={dimensions}
                        onLoad={handleImageLoad}
                        maxHeight={previewMaxHeight}
                        padding={renderPadding}
                      />
                    ) : (
                      <Text type="secondary">{renderEmptyMessage}</Text>
                    )}
                  </div>
                </div>
              ),
            },
            ...(showCodeTab ? [{
              key: 'code',
              label: 'Code',
              children: (
                <div style={variant === 'fill'
                  ? { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }
                  : { height: contentHeight, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                  <CodeViewer
                    label="Code"
                    content={resolvedCode}
                    placeholder={codePlaceholder}
                    copyMessage="Code copied"
                    loading={codeLoading}
                    fullHeight={true}
                  />
                </div>
              ),
            }] : []),
          ]}
          style={variant === 'fill' ? { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 } : undefined}
          className={variant === 'fill' ? 'tabs-fill' : undefined}
        />
      </div>
      {showCompare ? (
        <CompareModal
          open={compareOpen}
          onClose={() => setCompareOpen(false)}
          title={title}
          sourceUrl={sourceUrl}
          renderUrl={pngUrl}
          loading={effectiveLoading}
          origDimensions={origDimensions}
          renderDimensions={dimensions}
          onOriginalLoad={handleOriginalLoad}
          onRenderLoad={handleImageLoad}
        />
      ) : null}
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

function CodeViewer({ label, content, placeholder, copyMessage, loading = false, fullHeight = false }) {
  const normalized = useMemo(() => (content ?? "").replace(/\r\n/g, "\n"), [content]);
  const hasContent = normalized.length > 0;

  const handleCopy = async () => {
    if (!hasContent || loading) return;
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
    <div className="codeEditor" style={fullHeight ? { height: '100%', display: 'flex', flexDirection: 'column' } : undefined}>
      <div className="codeEditorToolbar">
        <div className="codeEditorDots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
        <Tooltip title={hasContent && !loading ? "Copy" : loading ? "Loading" : "Nothing to copy"}>
          <Button size="small" type="text" onClick={handleCopy} disabled={!hasContent || loading}>
            Copy
          </Button>
        </Tooltip>
      </div>
      <div className="codeEditorBody" style={fullHeight ? { flex: 1, overflow: 'auto', maxHeight: 'none' } : undefined}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: fullHeight ? '100%' : 180 }}>
            <Spin />
          </div>
        ) : (
          <pre className={`codeEditorContent${hasContent ? "" : " codeEditorEmpty"}`} style={fullHeight ? { height: '100%' } : undefined}>
            {hasContent ? normalized : placeholder || ""}
          </pre>
        )}
      </div>
    </div>
  );
}
