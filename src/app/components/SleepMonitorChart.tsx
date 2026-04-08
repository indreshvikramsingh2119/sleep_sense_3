import { Button } from "./ui/button";
import { Play, Pause, SkipBack, SkipForward, Maximize2, Settings, Download, FileText } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "./ui/alert-dialog";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import type { Patient, RawDataEntry } from "./PatientInfo";

// Generate continuous signal data
const generateSignalData = (points: number, frequency: number, amplitude: number, offset: number = 0) => {
  return Array.from({ length: points }, (_, i) => ({
    time: i,
    value: Math.sin(i * frequency) * amplitude + offset + (Math.random() - 0.5) * amplitude * 0.1,
  }));
};

const timePoints = 300;

const abdominalData = generateSignalData(timePoints, 0.05, 15, 50);
const bodyMoveData = generateSignalData(timePoints, 0.03, 20, 50);
const snoringData = generateSignalData(timePoints, 0.1, 25, 50);
const apneaData = generateSignalData(timePoints, 0.02, 10, 30);
const spo2Data = generateSignalData(timePoints, 0.01, 5, 95);
const pulseWaveData = generateSignalData(timePoints, 0.15, 30, 70);
const bodyPosData = Array.from({ length: timePoints }, (_, i) => ({
  time: i,
  value: i > 100 && i < 150 ? 80 : i > 200 && i < 250 ? 80 : 20,
}));
const cpapPressData = Array.from({ length: timePoints }, (_, i) => ({
  time: i,
  value: i < 100 ? 15 : 35,
}));

interface SignalTraceProps {
  data: Array<{ time: number; value: number }>;
  color: string;
  label: string;
  showGrid?: boolean;
  height: number;
  gradientId: string;
}

function SignalTrace({ data, color, label, showGrid = true, height, gradientId }: SignalTraceProps) {
  return (
    <div className="relative border-b border-gray-200" style={{ height: `${height}px` }}>
      <div className="absolute left-3 top-2 text-xs font-semibold text-gray-700 z-10 bg-white/90 backdrop-blur-sm px-3 py-1 rounded-lg border border-gray-200 shadow-sm">
        {label}
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.2}/>
              <stop offset="95%" stopColor={color} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid 
            stroke="#e5e7eb" 
            strokeDasharray="3 3" 
            horizontal={showGrid}
            vertical={true}
            verticalPoints={[30, 60, 90, 120, 150, 180, 210, 240, 270]}
          />
          <XAxis 
            dataKey="time" 
            hide={true}
            domain={[0, timePoints]}
          />
          <YAxis hide={true} domain={[0, 100]} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            fill={`url(#${gradientId})`}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SleepMonitorChart({
  patient,
  onRawDataSaved,
}: {
  patient: Patient;
  onRawDataSaved: (entry: RawDataEntry) => void;
}) {
  const currentTime = "23:04:00";
  const startTime = "22:04:00";

  const handleSaveYes = () => {
    const timestampIso = new Date().toISOString();
    const safeTimestamp = timestampIso.replace(/[:.]/g, "-");
    const fileName = `raw_data_${patient.patientId}_${safeTimestamp}.json`;
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

    const payload = {
      patient: {
        patientId: patient.patientId,
        name: patient.name,
        age: patient.age,
        gender: patient.gender,
      },
      timestamp: timestampIso,
      channels: {
        abdominalMove: abdominalData,
        bodyMove: bodyMoveData,
        snoring: snoringData,
        apnea: apneaData,
        spO2: spo2Data,
        pulseWave: pulseWaveData,
        bodyPos: bodyPosData,
        cpapPress: cpapPressData,
      },
      timePoints,
    };

    const content = JSON.stringify(payload, null, 2);
    const entry: RawDataEntry = {
      id,
      timestamp: timestampIso,
      fileName,
      content,
    };

    onRawDataSaved(entry);

    // Also download the file immediately.
    const blob = new Blob([content], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <div className="h-full flex flex-col">
      {/* Medical Control Bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-white rounded-lg p-1 border border-gray-200 shadow-sm">
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-gray-600 hover:bg-gray-100 rounded-md">
              <SkipBack className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-white hover:bg-blue-700 rounded-md bg-blue-600 shadow-md">
              <Play className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-gray-600 hover:bg-gray-100 rounded-md">
              <SkipForward className="w-4 h-4" />
            </Button>
          </div>
          
          <div className="h-6 w-px bg-gray-300"></div>
          
          <select className="text-sm bg-white border border-gray-300 rounded-lg px-3 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm">
            <option>Sleep Monitoring Report</option>
            <option>Detailed Analysis</option>
            <option>Event Summary</option>
          </select>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-700 hover:bg-gray-100 rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-700 hover:bg-gray-100 rounded-lg border border-gray-200 bg-white shadow-sm"
              >
                <FileText className="w-4 h-4 mr-2" />
                Save
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Save raw data?</AlertDialogTitle>
                <AlertDialogDescription>
                  This generates a timestamped raw-data JSON file from the current session.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleSaveYes}>Yes</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <Button variant="ghost" size="sm" className="text-gray-700 hover:bg-gray-100 rounded-lg border border-gray-200 bg-white shadow-sm">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Button variant="ghost" size="sm" className="text-gray-700 hover:bg-gray-100 rounded-lg border border-gray-200 bg-white shadow-sm">
            <Maximize2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="flex-1 relative overflow-hidden bg-white">
        {/* Medical watermark */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[140px] font-black text-gray-100 z-0 pointer-events-none select-none tracking-wider">
          60<span className="text-blue-100">S</span>
        </div>

        {/* Time stamps */}
        <div className="absolute top-3 left-4 text-xs font-mono text-gray-700 z-10 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-200 shadow-sm">
          <span className="text-blue-600 font-semibold">Start:</span> {startTime}
        </div>
        <div className="absolute top-3 right-4 text-xs font-mono text-gray-700 z-10 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200 shadow-sm">
          <span className="text-emerald-600 font-semibold">Current:</span> {currentTime}
        </div>

        {/* Signal Traces */}
        <div className="h-full flex flex-col pt-12">
          <SignalTrace data={abdominalData} color="#3b82f6" label="Abdominal Move" height={70} gradientId="grad1" />
          <SignalTrace data={bodyMoveData} color="#8b5cf6" label="Body Move" height={70} gradientId="grad2" />
          <SignalTrace data={snoringData} color="#ef4444" label="Snoring" height={80} gradientId="grad3" />
          <SignalTrace data={apneaData} color="#f59e0b" label="Apnea" height={60} showGrid={false} gradientId="grad4" />
          <SignalTrace data={spo2Data} color="#10b981" label="SpO2" height={60} gradientId="grad5" />
          <SignalTrace data={pulseWaveData} color="#06b6d4" label="Pulse Wave" height={80} gradientId="grad6" />
          <SignalTrace data={bodyPosData} color="#f97316" label="Body Pos" height={60} showGrid={false} gradientId="grad7" />
          <SignalTrace data={cpapPressData} color="#8b5cf6" label="CPAP Press" height={60} showGrid={false} gradientId="grad8" />
        </div>

        {/* Medical Status Bar */}
        <div className="absolute bottom-0 left-0 right-0 bg-gray-50 border-t border-gray-200 flex items-center justify-between px-6 py-2 shadow-inner">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-white px-3 py-1 rounded-lg border border-emerald-200 shadow-sm">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              <span className="text-xs font-mono text-gray-700 font-semibold">Recording</span>
            </div>
            <span className="text-xs font-mono text-gray-600">Stage: 1</span>
            <span className="text-xs font-mono text-gray-600">2025-05-03 23:04:00</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-gray-600">
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Duration:</span>
              <span className="font-mono text-gray-900 font-semibold">08:19</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Tracing:</span>
              <span className="font-mono text-gray-900 font-semibold">1/2</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Seconds:</span>
              <span className="font-mono text-gray-900 font-semibold">1/7140</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}