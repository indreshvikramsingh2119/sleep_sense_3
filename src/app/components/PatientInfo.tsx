import { User, Calendar, Heart, Moon, FileText, Activity, TrendingUp, Zap, Download } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Button } from "./ui/button";

export type Patient = {
  name: string;
  age: number;
  gender: string;
  patientId: string;
  lastVisit: string;
  avgSleepHours: number;
  sleepQuality: string;
};

export type RawDataEntry = {
  id: string;
  timestamp: string; // ISO string
  fileName: string;
  content: string; // raw file content (json string)
};

interface PatientInfoProps {
  patient: Patient;
  rawDataFiles: RawDataEntry[];
}

export function PatientInfo({ patient, rawDataFiles }: PatientInfoProps) {
  const handleDownloadRawData = (entry: RawDataEntry) => {
    const blob = new Blob([entry.content], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = entry.fileName;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    // Revoke after the click to free memory.
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <div className="h-full flex flex-col">
      <Tabs defaultValue="info" className="h-full flex flex-col">
        <TabsList className="grid w-full grid-cols-1 mb-4 bg-gray-100 p-1 rounded-xl border border-gray-200">
          <TabsTrigger 
            value="info" 
            className="rounded-lg data-[state=active]:bg-white data-[state=active]:text-blue-700 data-[state=active]:shadow-sm text-gray-600 font-medium"
          >
            Patient Info
          </TabsTrigger>
        </TabsList>

        <TabsContent value="info" className="flex-1 overflow-auto mt-0">
          <div className="h-full flex flex-col space-y-5">
            {/* Patient Avatar and Name */}
            <div className="flex flex-col items-center gap-3 pb-5 border-b border-gray-200">
              <div className="relative">
                <Avatar className="w-20 h-20 border-4 border-blue-100 shadow-md">
                  <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${patient.name}`} />
                  <AvatarFallback className="bg-gradient-to-br from-blue-600 to-blue-700 text-white text-xl font-semibold">
                    {patient.name.split(' ').map(n => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-emerald-500 rounded-full border-3 border-white flex items-center justify-center shadow-md">
                  <Activity className="w-3 h-3 text-white" />
                </div>
              </div>
              <div className="text-center">
                <h2 className="text-xl font-bold text-gray-900 mb-1">{patient.name}</h2>
                <p className="text-xs text-gray-600 bg-blue-50 px-3 py-1 rounded-full border border-blue-200">ID: {patient.patientId}</p>
              </div>
            </div>

            {/* Patient Details */}
            <div className="space-y-3">
              <div className="group bg-gradient-to-r from-blue-50 to-transparent rounded-xl p-3 border border-blue-100 hover:shadow-md transition-all duration-300 hover:scale-[1.02]">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shrink-0 shadow-sm">
                    <User className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-600 font-medium">Age / Gender</p>
                    <p className="text-sm font-semibold text-gray-900">{patient.age} years / {patient.gender}</p>
                  </div>
                </div>
              </div>

              <div className="group bg-gradient-to-r from-indigo-50 to-transparent rounded-xl p-3 border border-indigo-100 hover:shadow-md transition-all duration-300 hover:scale-[1.02]">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center shrink-0 shadow-sm">
                    <Calendar className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-600 font-medium">Last Visit</p>
                    <p className="text-sm font-semibold text-gray-900">{patient.lastVisit}</p>
                  </div>
                </div>
              </div>

              <div className="group bg-gradient-to-r from-purple-50 to-transparent rounded-xl p-3 border border-purple-100 hover:shadow-md transition-all duration-300 hover:scale-[1.02]">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shrink-0 shadow-sm">
                    <Moon className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-600 font-medium">Avg Sleep Duration</p>
                    <p className="text-sm font-semibold text-gray-900">{patient.avgSleepHours} hours/night</p>
                  </div>
                </div>
              </div>

              <div className="group bg-gradient-to-r from-emerald-50 to-transparent rounded-xl p-3 border border-emerald-100 hover:shadow-md transition-all duration-300 hover:scale-[1.02]">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shrink-0 shadow-sm">
                    <Heart className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-600 font-medium">Sleep Quality</p>
                    <p className="text-sm font-semibold text-gray-900">{patient.sleepQuality}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Inline Raw Data Files */}
            <div className="pt-4 border-t border-gray-200 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-600" />
                  Raw data file
                </h3>
                <span className="text-xs text-blue-600 font-medium">
                  {rawDataFiles.length}
                </span>
              </div>

              {rawDataFiles.length === 0 ? (
                <p className="text-xs text-gray-500">
                  Press <span className="font-semibold">Save</span> to generate raw data with a timestamp.
                </p>
              ) : (
                <div className="space-y-2">
                  {rawDataFiles.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-start justify-between gap-3 p-3 bg-gray-50 rounded-xl border border-gray-200 hover:bg-blue-50 transition-all"
                    >
                      <div className="min-w-0">
                        <p className="text-[11px] text-gray-600 font-medium">Saved raw data</p>
                        <p className="text-xs text-gray-900 font-semibold truncate" title={entry.fileName}>
                          {entry.fileName}
                        </p>
                        <p className="text-[11px] text-gray-500 mt-1">
                          {new Date(entry.timestamp).toLocaleString()}
                        </p>
                      </div>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDownloadRawData(entry)}
                        className="text-blue-600 hover:bg-blue-50 shrink-0"
                      >
                        <Download className="w-3 h-3 mr-1" />
                        Download
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Stats Cards */}
            <div className="pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-blue-600" />
                  Weekly Summary
                </h3>
                <Zap className="w-4 h-4 text-amber-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-3 border border-blue-200 hover:shadow-md transition-all">
                  <p className="text-xs text-blue-700 font-medium mb-1">Total Sleep</p>
                  <p className="text-xl font-bold text-blue-900">48.5 <span className="text-xs text-blue-600">hrs</span></p>
                </div>
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-3 border border-purple-200 hover:shadow-md transition-all">
                  <p className="text-xs text-purple-700 font-medium mb-1">Deep Sleep</p>
                  <p className="text-xl font-bold text-purple-900">12.3 <span className="text-xs text-purple-600">hrs</span></p>
                </div>
                <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl p-3 border border-indigo-200 hover:shadow-md transition-all">
                  <p className="text-xs text-indigo-700 font-medium mb-1">REM Sleep</p>
                  <p className="text-xl font-bold text-indigo-900">10.8 <span className="text-xs text-indigo-600">hrs</span></p>
                </div>
                <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-xl p-3 border border-emerald-200 hover:shadow-md transition-all">
                  <p className="text-xs text-emerald-700 font-medium mb-1">Efficiency</p>
                  <p className="text-xl font-bold text-emerald-900">87<span className="text-xs text-emerald-600">%</span></p>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}