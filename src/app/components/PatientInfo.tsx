import { User, Calendar, Heart, Moon, Upload, Download, FileText, Activity, TrendingUp, Zap } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Button } from "./ui/button";
import { useState } from "react";

interface PatientInfoProps {
  patient: {
    name: string;
    age: number;
    gender: string;
    patientId: string;
    lastVisit: string;
    avgSleepHours: number;
    sleepQuality: string;
  };
}

export function PatientInfo({ patient }: PatientInfoProps) {
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([
    "sleep_data_2026-04-01.csv",
    "sleep_data_2026-04-02.csv",
    "sleep_data_2026-04-03.csv",
  ]);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const newFiles = Array.from(files).map(file => file.name);
      setUploadedFiles([...uploadedFiles, ...newFiles]);
    }
  };

  const handleDownload = (filename: string) => {
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent('Mock sleep data for ' + filename));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="h-full flex flex-col">
      <Tabs defaultValue="info" className="h-full flex flex-col">
        <TabsList className="grid w-full grid-cols-2 mb-4 bg-gray-100 p-1 rounded-xl border border-gray-200">
          <TabsTrigger 
            value="info" 
            className="rounded-lg data-[state=active]:bg-white data-[state=active]:text-blue-700 data-[state=active]:shadow-sm text-gray-600 font-medium"
          >
            Patient Info
          </TabsTrigger>
          <TabsTrigger 
            value="data"
            className="rounded-lg data-[state=active]:bg-white data-[state=active]:text-blue-700 data-[state=active]:shadow-sm text-gray-600 font-medium"
          >
            Raw Data
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

        <TabsContent value="data" className="flex-1 overflow-auto mt-0">
          <div className="h-full flex flex-col space-y-4">
            {/* Upload Area */}
            <div className="relative group">
              <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center bg-gray-50 hover:bg-blue-50 hover:border-blue-400 transition-all">
                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                  <Upload className="w-6 h-6 text-white" />
                </div>
                <p className="text-sm font-semibold text-gray-900 mb-1">Import Raw Data</p>
                <p className="text-xs text-gray-600 mb-4">
                  Upload CSV, EDF, or TXT files
                </p>
                <label htmlFor="file-upload">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    asChild
                    className="bg-blue-600 text-white border-blue-600 hover:bg-blue-700 hover:border-blue-700"
                  >
                    <span className="cursor-pointer">
                      <Upload className="w-3 h-3 mr-2" />
                      Choose Files
                    </span>
                  </Button>
                </label>
                <input
                  id="file-upload"
                  type="file"
                  multiple
                  accept=".csv,.edf,.txt"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </div>
            </div>

            {/* File List */}
            <div className="flex-1 overflow-auto">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 text-sm">
                  Uploaded Files <span className="text-blue-600">({uploadedFiles.length})</span>
                </h3>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => uploadedFiles.forEach(file => handleDownload(file))}
                  className="text-blue-600 hover:bg-blue-50"
                >
                  <Download className="w-3 h-3 mr-1" />
                  All
                </Button>
              </div>
              <div className="space-y-2">
                {uploadedFiles.map((file, index) => (
                  <div 
                    key={index}
                    className="group flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-200 hover:bg-blue-50 hover:border-blue-300 transition-all hover:shadow-sm"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shrink-0 shadow-sm">
                        <FileText className="w-4 h-4 text-white" />
                      </div>
                      <span className="text-xs text-gray-700 truncate font-medium">{file}</span>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0 shrink-0 text-blue-600 hover:bg-blue-100 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => handleDownload(file)}
                    >
                      <Download className="w-3 h-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Download All Button */}
            <div className="pt-3 border-t border-gray-200">
              <Button 
                className="w-full bg-blue-600 hover:bg-blue-700 text-white border-none shadow-md rounded-xl"
                onClick={() => alert('Downloading all files as ZIP...')}
              >
                <Download className="w-4 h-4 mr-2" />
                Download All as ZIP
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}