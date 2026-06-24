#!/usr/bin/env python3
"""
Sleep Sense AI Models Orchestrator
Train and predict with multiple AI models
"""

import os
import subprocess
import sys
from pathlib import Path

# Get project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

class AIModelOrchestrator:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.models = {
            'cnn': {
                'name': 'Convolutional Neural Network',
                'train': 'train.py',
                'predict': 'predict.py',
                'path': 'ai_models'
            },
            'knn': {
                'name': 'K-Nearest Neighbors',
                'train': 'knn/train_knn.py',
                'predict': 'knn/predict_knn.py',
                'path': 'ai_models'
            },
            'vit': {
                'name': 'Vision Transformer',
                'train': 'vit/train_vit.py',
                'predict': 'vit/predict_vit.py',
                'path': 'ai_models'
            },
        }
    
    def train_model(self, model_name):
        """Train a specific model"""
        if model_name not in self.models:
            print(f"❌ Model '{model_name}' not found")
            return False
        
        model_info = self.models[model_name]
        script_path = os.path.join(self.project_root, model_info['path'], model_info['train'])
        
        print(f"\n{'='*60}")
        print(f"🚀 Training {model_info['name']}...")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                ['python3', script_path],
                cwd=self.project_root,
                check=True
            )
            print(f"✅ {model_info['name']} trained successfully!\n")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Training failed for {model_info['name']}: {e}\n")
            return False
    
    def predict_model(self, model_name):
        """Make predictions with a specific model"""
        if model_name not in self.models:
            print(f"❌ Model '{model_name}' not found")
            return False
        
        model_info = self.models[model_name]
        script_path = os.path.join(self.project_root, model_info['path'], model_info['predict'])
        
        print(f"\n{'='*60}")
        print(f"🔮 Predicting with {model_info['name']}...")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                ['python3', script_path],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
            if result.stderr:
                print("Warnings:", result.stderr)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Prediction failed for {model_info['name']}: {e}\n")
            if e.stdout:
                print("Output:", e.stdout)
            return False
    
    def train_all(self):
        """Train all models"""
        print("\n" + "🎯 "*20)
        print("TRAINING ALL MODELS")
        print("🎯 "*20)
        
        results = {}
        for model_name in self.models:
            results[model_name] = self.train_model(model_name)
        
        print("\n" + "="*60)
        print("TRAINING SUMMARY")
        print("="*60)
        for model_name, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"{self.models[model_name]['name']}: {status}")
        print("="*60 + "\n")
    
    def predict_all(self):
        """Make predictions with all models"""
        print("\n" + "🎯 "*20)
        print("PREDICTING WITH ALL MODELS")
        print("🎯 "*20)
        
        results = {}
        for model_name in self.models:
            results[model_name] = self.predict_model(model_name)
        
        print("\n" + "="*60)
        print("PREDICTION SUMMARY")
        print("="*60)
        for model_name, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"{self.models[model_name]['name']}: {status}")
        print("="*60 + "\n")
    
    def show_menu(self):
        """Show interactive menu"""
        while True:
            print("\n" + "="*60)
            print("SLEEP SENSE AI MODELS ORCHESTRATOR")
            print("="*60)
            print("1. Train CNN")
            print("2. Train KNN")
            print("3. Train Vision Transformer (ViT)")
            print("4. Train All Models")
            print("5. Predict with CNN")
            print("6. Predict with KNN")
            print("7. Predict with ViT")
            print("8. Predict with All Models")
            print("0. Exit")
            print("="*60)
            
            choice = input("Enter your choice (0-8): ").strip()
            
            if choice == "0":
                print("Goodbye! 👋")
                break
            elif choice == "1":
                self.train_model('cnn')
            elif choice == "2":
                self.train_model('knn')
            elif choice == "3":
                self.train_model('vit')
            elif choice == "4":
                self.train_all()
            elif choice == "5":
                self.predict_model('cnn')
            elif choice == "6":
                self.predict_model('knn')
            elif choice == "7":
                self.predict_model('vit')
            elif choice == "8":
                self.predict_all()
            else:
                print("❌ Invalid choice. Try again.")

if __name__ == "__main__":
    orchestrator = AIModelOrchestrator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "train_all":
            orchestrator.train_all()
        elif command == "predict_all":
            orchestrator.predict_all()
        elif command.startswith("train_"):
            model_name = command.replace("train_", "")
            orchestrator.train_model(model_name)
        elif command.startswith("predict_"):
            model_name = command.replace("predict_", "")
            orchestrator.predict_model(model_name)
        else:
            print(f"Unknown command: {command}")
            print(
                "Usage: python3 orchestrator.py "
                "[train_all|predict_all|train_<model>|predict_<model>]"
            )
    else:
        orchestrator.show_menu()
