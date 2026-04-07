import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const sleepDurationData = [
  { date: "Mon", hours: 7.2, target: 8 },
  { date: "Tue", hours: 6.8, target: 8 },
  { date: "Wed", hours: 7.5, target: 8 },
  { date: "Thu", hours: 6.5, target: 8 },
  { date: "Fri", hours: 8.1, target: 8 },
  { date: "Sat", hours: 8.4, target: 8 },
  { date: "Sun", hours: 7.8, target: 8 },
];

const sleepStagesData = [
  { date: "Mon", deep: 1.5, light: 4.2, rem: 1.5 },
  { date: "Tue", deep: 1.3, light: 3.8, rem: 1.4 },
  { date: "Wed", deep: 1.8, light: 4.0, rem: 1.7 },
  { date: "Thu", deep: 1.2, light: 3.5, rem: 1.3 },
  { date: "Fri", deep: 2.0, light: 4.3, rem: 1.8 },
  { date: "Sat", deep: 2.1, light: 4.5, rem: 1.8 },
  { date: "Sun", deep: 1.9, light: 4.1, rem: 1.8 },
];

const sleepQualityData = [
  { name: "Deep", value: 25, color: "#8b5cf6" },
  { name: "Light", value: 50, color: "#3b82f6" },
  { name: "REM", value: 20, color: "#06b6d4" },
  { name: "Awake", value: 5, color: "#ef4444" },
];

const heartRateData = [
  { time: "22:00", bpm: 65 },
  { time: "23:00", bpm: 62 },
  { time: "00:00", bpm: 58 },
  { time: "01:00", bpm: 55 },
  { time: "02:00", bpm: 54 },
  { time: "03:00", bpm: 53 },
  { time: "04:00", bpm: 54 },
  { time: "05:00", bpm: 56 },
  { time: "06:00", bpm: 60 },
];

export function SleepCharts() {
  return (
    <div className="grid grid-cols-2 gap-4 h-full">
      {/* Sleep Duration Chart - Top Left */}
      <Card className="flex flex-col">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Sleep Duration</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 pb-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sleepDurationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 12 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '12px' }}
              />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Line
                type="monotone"
                dataKey="hours"
                stroke="#8b5cf6"
                strokeWidth={2}
                name="Sleep (hrs)"
                dot={{ fill: '#8b5cf6', r: 3 }}
              />
              <Line
                type="monotone"
                dataKey="target"
                stroke="#6b7280"
                strokeDasharray="5 5"
                name="Target"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Sleep Stages Chart - Top Right */}
      <Card className="flex flex-col">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Sleep Stages</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 pb-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sleepStagesData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 12 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '12px' }}
              />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Bar dataKey="deep" stackId="a" fill="#8b5cf6" name="Deep" />
              <Bar dataKey="light" stackId="a" fill="#3b82f6" name="Light" />
              <Bar dataKey="rem" stackId="a" fill="#06b6d4" name="REM" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Sleep Quality Pie Chart - Bottom Left */}
      <Card className="flex flex-col">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Sleep Quality</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 pb-2">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={sleepQualityData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ value }) => `${value}%`}
                outerRadius="80%"
                fill="#8884d8"
                dataKey="value"
              >
                {sleepQualityData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: '12px' }} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Heart Rate Chart - Bottom Right */}
      <Card className="flex flex-col">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Heart Rate During Sleep</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 pb-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={heartRateData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 12 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '12px' }}
              />
              <Area
                type="monotone"
                dataKey="bpm"
                stroke="#ef4444"
                fill="#fee2e2"
                strokeWidth={2}
                name="BPM"
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}