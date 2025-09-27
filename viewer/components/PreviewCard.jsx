import { Card, Tabs, Typography, Button, Modal, message, Tooltip } from "antd";
import { useMemo, useState } from "react";

const { Text } = Typography;

export default function PreviewCard({ title, ext, code, prompt, sourceUrl }) {
  const [compareOpen, setCompareOpen] = useState(false);
  const htmlDoc = useMemo(() => {
    if (ext === ".html") return code;
    if (ext !== ".jsx") return `<!doctype html><html><body><pre style="font:12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space:pre-wrap; padding:12px;">${escapeHtml(code||"")}</pre></body></html>`;
    const jsx = (code || "").replace(/^\s*export\s+default\s+function\s+/m, "function ");
    const safeJSX = jsx.replace(/<\/(script)>/gi, "</" + "script>");
    return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; img-src data: https:; font-src data: https:; connect-src https://unpkg.com https://cdn.tailwindcss.com; object-src 'none'; base-uri 'none';" />
  <style>
    html,body,#root{height:100%} body{margin:0;background:#ffffff;display:flex;align-items:center;justify-content:center}
  </style>
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
  <script crossorigin src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script>
    (function(){
      const names = ["Sun","Moon","Cloud","CloudSun","CloudMoon","Rain","Snowflake","MapPin","Bell","Heart","Star","Search","Calendar","Clock","ChevronRight","ChevronLeft","ChevronDown","ChevronUp","Camera","Phone","Wifi","Battery","Bluetooth","Music","Play","Pause","Volume","Settings","User","Home","MessageCircle"]; 
      const Icon = (props)=> React.createElement('div', {style:{display:'inline-block',width:(props.size||16)+'px',height:(props.size||16)+'px',border:'1px solid #D1D5DB',borderRadius:'4px'}},'');
      names.forEach(n => { window[n] = Icon; });
    })();
  </script>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
${safeJSX}
try {
  const root = ReactDOM.createRoot(document.getElementById('root'));
  const Comp = typeof Widget !== 'undefined' ? Widget : (typeof exports !== 'undefined' && exports.default ? exports.default : null);
  if (Comp) root.render(React.createElement(Comp));
} catch (e) { document.body.innerHTML = '<pre style="padding:16px;color:#ef4444">'+(e && e.stack || e)+'</pre>'; }
  </script>
</body>
</html>`;
  }, [code, ext]);

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
              <div className="iframeWrap">
                <iframe
                  title={title}
                  srcDoc={htmlDoc}
                  style={{ width: "100%", height: 420, border: 0, borderRadius: 8, background: "#fff" }}
                  sandbox="allow-scripts"
                  referrerPolicy="no-referrer"
                />
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
            <div className="iframeWrap" style={{ border: "1px solid #eef0f3", borderRadius: 8 }}>
              <iframe
                title={`compare-${title}`}
                srcDoc={htmlDoc}
                style={{ width: "100%", height: 420, border: 0, borderRadius: 8, background: "#fff" }}
                sandbox="allow-scripts"
                referrerPolicy="no-referrer"
              />
            </div>
          </div>
        </div>
      </Modal>
    </Card>
  );
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
}

function CodeViewer({ label, content, placeholder, copyMessage }) {
  const normalized = useMemo(() => (content ?? "").replace(/\r\n/g, "\n"), [content]);
  const hasContent = normalized.length > 0;
  const lines = useMemo(() => (hasContent ? normalized.split("\n") : [""]), [normalized, hasContent]);

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
        <pre className="codeEditorGutter" aria-hidden="true">
          {lines.map((_, idx) => (
            <span key={idx}>{idx + 1}</span>
          ))}
        </pre>
        <pre className={`codeEditorContent${hasContent ? "" : " codeEditorEmpty"}`}>
          {hasContent ? normalized : placeholder || ""}
        </pre>
      </div>
    </div>
  );
}
