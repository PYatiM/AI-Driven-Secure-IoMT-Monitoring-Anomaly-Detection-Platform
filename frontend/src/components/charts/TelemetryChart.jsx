import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const formatXAxis = (value) => {
  const parsed = new Date(value);
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const TelemetryChart = ({ data, title, metricName }) => {
  return (
    <div className="chart-panel">
      <div className="panel-header">
        <h3>{title}</h3>
        <p>{metricName || "Metric stream"}</p>
      </div>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="4 4" />
            <XAxis dataKey="recordedAt" tickFormatter={formatXAxis} />
            <YAxis />
            <Tooltip
              labelFormatter={(label) =>
                new Date(label).toLocaleString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  day: "2-digit",
                  month: "short",
                })
              }
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--chart-line)"
              strokeWidth={2.5}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TelemetryChart;

