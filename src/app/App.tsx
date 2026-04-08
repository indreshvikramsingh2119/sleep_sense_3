import { Moon, Activity, Stethoscope } from "lucide-react";
import { useState } from "react";
import { PatientInfo, type Patient, type RawDataEntry } from "./components/PatientInfo";
import { SleepMonitorChart } from "./components/SleepMonitorChart";

export default function App() {
  const patient: Patient = {
    name: "Sarah Johnson",
    age: 34,
    gender: "Female",
    patientId: "SS-2024-1847",
    lastVisit: "April 4, 2026",
    avgSleepHours: 7.2,
    sleepQuality: "Good",
  };

  const [rawDataFiles, setRawDataFiles] = useState<RawDataEntry[]>([]);

  const handleRawDataSaved = (entry: RawDataEntry) => {
    setRawDataFiles((prev) => [entry, ...prev]);
  };

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100">
      {/* Medical Grade Header */}
      <header className="bg-white border-b-2 border-blue-100 shadow-sm shrink-0">
        <div className="px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center shadow-md">
                  <Stethoscope className="w-6 h-6 text-white" />
                </div>
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full border-2 border-white"></div>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Sleep Sense</h1>
                <p className="text-sm text-gray-600 flex items-center gap-2">
                  <Activity className="w-3 h-3" />
                  Medical Sleep Monitoring System
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="px-4 py-2 rounded-lg bg-blue-50 border border-blue-200">
                <span className="text-xs text-gray-600">Live Session</span>
                <p className="text-sm font-semibold text-blue-700">23:45:12</p>
              </div>
              <div className="px-4 py-2 rounded-lg bg-emerald-50 border border-emerald-200">
                <span className="text-xs text-gray-600">Status</span>
                <p className="text-sm font-semibold text-emerald-700">● Active</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden p-6">
        <div className="h-full flex gap-6">
          {/* Left Side - Patient Info */}
          <div className="w-96 shrink-0 bg-white rounded-2xl border border-gray-200 shadow-lg p-6">
            <PatientInfo patient={patient} rawDataFiles={rawDataFiles} />
          </div>

          {/* Right Side - Monitor Chart */}
          <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-lg overflow-hidden">
            <SleepMonitorChart patient={patient} onRawDataSaved={handleRawDataSaved} />
          </div>
        </div>
      </main>
    </div>
  );
}