import { Select, Tag } from "antd";

export default function RunPicker({ runs, value, onChange }) {
  const options = runs.map((r) => ({
    label: (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>{r.name}</span>
        {r.model ? <Tag color="blue" style={{ marginInline: 0 }}>{r.model}</Tag> : null}
        {r.experiment ? <Tag color="geekblue" style={{ marginInline: 0 }}>{r.experiment}</Tag> : null}
      </div>
    ),
    value: r.name,
  }));
  return (
    <Select
      showSearch
      style={{ minWidth: 360 }}
      placeholder="Pick a run"
      optionFilterProp="label"
      value={value}
      options={options}
      onChange={onChange}
    />
  );
}

