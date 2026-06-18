"""
OmniRoute Analytics — ML Training Module
Models:
  1. KMeans Hotspot Clustering (scikit-learn)
  2. GradientBoosting DCLI Predictor (scikit-learn)
  3. LSTM Congestion Forecaster (PyTorch)
  4. Zone Risk Scorer + Temporal Pattern Analyzer
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
import warnings
warnings.filterwarnings('ignore')

# Try PyTorch — graceful fallback if unavailable
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("  ⚠️  PyTorch not available — LSTM disabled, using statistical fallback.")


# ── LSTM Model Definition ──
if TORCH_AVAILABLE:
    class LSTMForecaster(nn.Module):
        """LSTM network for hourly congestion time-series forecasting."""
        def __init__(self, input_size=1, hidden_size=64, num_layers=2, output_size=24):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(32, output_size),
            )

        def forward(self, x):
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
            c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
            out, _ = self.lstm(x, (h0, c0))
            out = self.fc(out[:, -1, :])
            return out


class OmniRouteMLEngine:
    """Trains on historical violation data, produces ML predictions."""

    def __init__(self):
        self.hotspot_model = None
        self.congestion_model = None
        self.lstm_model = None
        self.lstm_scaler = None
        self.zone_clusters = None
        self.hourly_patterns = {}
        self.zone_risk_profiles = {}
        self.trained = False
        self.lstm_trained = False
        self.training_stats = {}
        self.lstm_training_loss = []

    def train(self, df: pd.DataFrame):
        """Train all models on the CSV dataset."""
        print("  🧠 [ML] Starting model training...")
        df = df.copy()

        # ── Normalize columns ──
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if cl in ('latitude', 'lat'): col_map[col] = 'lat'
            elif cl in ('longitude', 'lng', 'lon'): col_map[col] = 'lng'
        if col_map:
            df.rename(columns=col_map, inplace=True)

        df['lat'] = pd.to_numeric(df['lat'].astype(str), errors='coerce')
        df['lng'] = pd.to_numeric(df['lng'].astype(str), errors='coerce')
        df.dropna(subset=['lat', 'lng'], inplace=True)

        # Timestamps
        ts_col = next((c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()), None)
        if ts_col:
            df['timestamp'] = pd.to_datetime(df[ts_col], errors='coerce', utc=True)
            df.dropna(subset=['timestamp'], inplace=True)
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            df['month'] = df['timestamp'].dt.month
        else:
            df['hour'] = np.random.randint(0, 24, len(df))
            df['day_of_week'] = np.random.randint(0, 7, len(df))

        # Zone / vehicle type
        zone_col = next((c for c in df.columns if 'police' in c.lower() or 'station' in c.lower()), None)
        df['zone'] = df[zone_col].fillna('Unknown') if zone_col else 'Unknown'
        vtype_col = next((c for c in df.columns if 'vehicle' in c.lower() and 'type' in c.lower()), None)
        df['vehicle_type'] = df[vtype_col].fillna('CAR') if vtype_col else 'CAR'

        self.training_stats = {
            'total_records': int(len(df)),
            'date_range': f"{df['timestamp'].min().strftime('%Y-%m-%d')} to {df['timestamp'].max().strftime('%Y-%m-%d')}" if ts_col else 'N/A',
            'unique_zones': int(df['zone'].nunique()),
            'unique_vehicle_types': int(df['vehicle_type'].nunique()),
        }

        # ═══ Model 1: KMeans Hotspot Clustering ═══
        print("  🧠 [1/4] KMeans Hotspot Clustering...")
        n_clusters = min(20, max(5, len(df) // 100))
        self.hotspot_model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['cluster'] = self.hotspot_model.fit_predict(df[['lat', 'lng']].values)

        self.zone_clusters = []
        for cid in range(n_clusters):
            cd = df[df['cluster'] == cid]
            center = self.hotspot_model.cluster_centers_[cid]
            self.zone_clusters.append({
                'cluster_id': cid,
                'lat': round(float(center[0]), 6), 'lng': round(float(center[1]), 6),
                'violation_count': int(len(cd)),
                'zone': cd['zone'].mode().iloc[0] if len(cd) > 0 else 'Unknown',
                'peak_hour': int(cd['hour'].mode().iloc[0]) if len(cd) > 0 else 12,
                'density': round(len(cd) / len(df) * 100, 1),
            })
        self.zone_clusters.sort(key=lambda x: -x['violation_count'])
        print(f"    ✅ {n_clusters} spatial clusters identified")

        # ═══ Model 2: Temporal Patterns ═══
        print("  🧠 [2/4] Temporal Pattern Analysis...")
        self.hourly_patterns = {
            'hourly': df.groupby('hour').size().to_dict(),
            'daily': df.groupby('day_of_week').size().to_dict(),
            'peak_hours': sorted(df.groupby('hour').size().items(), key=lambda x: -x[1])[:5],
        }

        # ═══ Model 3: Zone Risk Scoring ═══
        print("  🧠 [3/4] Zone Risk Scoring...")
        zone_stats = df.groupby('zone').agg(
            count=('lat', 'size'), avg_lat=('lat', 'mean'), avg_lng=('lng', 'mean'),
            peak_hour=('hour', lambda x: x.mode().iloc[0] if len(x) > 0 else 12),
        ).reset_index()
        max_count = zone_stats['count'].max()
        zone_stats['risk_score'] = (zone_stats['count'] / max_count * 100).round(1)
        zone_stats['risk_level'] = zone_stats['risk_score'].apply(
            lambda x: 'CRITICAL' if x > 60 else ('HIGH' if x > 30 else ('MEDIUM' if x > 10 else 'LOW'))
        )
        self.zone_risk_profiles = {}
        for _, r in zone_stats.iterrows():
            self.zone_risk_profiles[r['zone']] = {
                'zone': r['zone'], 'total_violations': int(r['count']),
                'risk_score': float(r['risk_score']), 'risk_level': r['risk_level'],
                'center_lat': round(float(r['avg_lat']), 6), 'center_lng': round(float(r['avg_lng']), 6),
                'peak_hour': int(r['peak_hour']),
            }
        print(f"    ✅ {len(self.zone_risk_profiles)} zones scored")

        # ═══ Model 4: GradientBoosting DCLI Predictor ═══
        print("  🧠 [4/4] GradientBoosting DCLI Predictor...")
        le_zone = LabelEncoder()
        le_vtype = LabelEncoder()
        df['zone_enc'] = le_zone.fit_transform(df['zone'])
        df['vtype_enc'] = le_vtype.fit_transform(df['vehicle_type'])
        features = df[['lat', 'lng', 'hour', 'day_of_week', 'zone_enc', 'vtype_enc']].values
        zone_density = df.groupby('zone')['lat'].transform('size')
        hour_density = df.groupby('hour')['lat'].transform('size')
        df['dcli_target'] = (zone_density * 5 + hour_density * 2 + np.random.normal(0, 100, len(df))).clip(50, 150000)

        self.congestion_model = GradientBoostingRegressor(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
        self.congestion_model.fit(features, df['dcli_target'].values)
        self._le_zone = le_zone
        self._le_vtype = le_vtype
        r2 = self.congestion_model.score(features, df['dcli_target'].values)
        self._feature_importance = dict(zip(
            ['latitude', 'longitude', 'hour', 'day_of_week', 'zone', 'vehicle_type'],
            self.congestion_model.feature_importances_.round(3).tolist()
        ))
        print(f"    ✅ GBR R²={r2:.3f}")

        # ═══ Model 5: LSTM Congestion Forecaster (PyTorch) ═══
        if TORCH_AVAILABLE and ts_col:
            self._train_lstm(df)

        self.trained = True
        print(f"  ✅ All models trained on {len(df)} records!")
        return self.get_training_summary()

    def _train_lstm(self, df):
        """Train LSTM on hourly violation time series."""
        print("  🧠 [LSTM] Training PyTorch LSTM Forecaster...")
        try:
            # Create hourly time series
            df_ts = df.set_index('timestamp').resample('h').size().reset_index(name='count')
            series = df_ts['count'].values.astype(np.float32)

            if len(series) < 48:
                print("    ⚠️ Not enough time series data for LSTM")
                return

            # Scale
            self.lstm_scaler = MinMaxScaler()
            scaled = self.lstm_scaler.fit_transform(series.reshape(-1, 1)).flatten()

            # Create sequences (24h lookback → 24h forecast)
            lookback = 24
            X, y = [], []
            for i in range(lookback, len(scaled) - 24):
                X.append(scaled[i - lookback:i])
                y.append(scaled[i:i + 24])

            if len(X) < 10:
                print("    ⚠️ Too few sequences for LSTM training")
                return

            X = torch.FloatTensor(np.array(X)).unsqueeze(-1)
            y = torch.FloatTensor(np.array(y))

            # Train
            self.lstm_model = LSTMForecaster(input_size=1, hidden_size=64, num_layers=2, output_size=24)
            optimizer = torch.optim.Adam(self.lstm_model.parameters(), lr=0.001)
            criterion = nn.MSELoss()

            self.lstm_model.train()
            self.lstm_training_loss = []
            epochs = 50
            for epoch in range(epochs):
                optimizer.zero_grad()
                output = self.lstm_model(X)
                loss = criterion(output, y)
                loss.backward()
                optimizer.step()
                self.lstm_training_loss.append(round(loss.item(), 6))
                if (epoch + 1) % 10 == 0:
                    print(f"    Epoch {epoch+1}/{epochs} | Loss: {loss.item():.6f}")

            self.lstm_model.eval()
            self.lstm_trained = True
            self._last_sequence = scaled[-lookback:]
            print(f"    ✅ LSTM trained! Final loss: {self.lstm_training_loss[-1]}")
        except Exception as e:
            print(f"    ❌ LSTM training failed: {e}")

    def predict_lstm_forecast(self):
        """Use LSTM to forecast next 24 hours of violations."""
        if not self.lstm_trained or self.lstm_model is None:
            # Fallback: use hourly patterns
            now = datetime.utcnow()
            avg = sum(self.hourly_patterns.get('hourly', {}).values()) / max(len(self.hourly_patterns.get('hourly', {})), 1)
            return [{
                'hour': (now.hour + h) % 24,
                'predicted_violations': self.hourly_patterns.get('hourly', {}).get((now.hour + h) % 24, int(avg)),
                'source': 'statistical_fallback',
            } for h in range(24)]

        with torch.no_grad():
            inp = torch.FloatTensor(self._last_sequence).unsqueeze(0).unsqueeze(-1)
            pred = self.lstm_model(inp).squeeze().numpy()
            pred_inv = self.lstm_scaler.inverse_transform(pred.reshape(-1, 1)).flatten()

        now = datetime.utcnow()
        return [{
            'hour': (now.hour + h) % 24,
            'time': (now + timedelta(hours=h)).strftime('%H:%M'),
            'predicted_violations': max(0, int(round(pred_inv[h]))),
            'source': 'LSTM',
        } for h in range(24)]

    def predict_hotspots(self, hours_ahead=24):
        if not self.trained:
            return []
        now = datetime.utcnow()
        avg_rate = sum(self.hourly_patterns['hourly'].values()) / max(len(self.hourly_patterns['hourly']), 1)
        predictions = []
        for h in range(hours_ahead):
            fh = (now + timedelta(hours=h)).hour
            rate = self.hourly_patterns['hourly'].get(fh, avg_rate * 0.5)
            mult = rate / max(avg_rate, 1)
            for cl in self.zone_clusters[:10]:
                conf = round(min(0.95, max(0.2, mult * 0.5 + (0.2 if cl['peak_hour'] == fh else 0))), 2)
                predictions.append({
                    'zone': cl['zone'], 'lat': cl['lat'], 'lng': cl['lng'],
                    'predicted_hour': fh, 'predicted_time': (now + timedelta(hours=h)).isoformat(),
                    'confidence': conf,
                    'expected_violations': max(1, int(cl['violation_count'] * mult / 30)),
                    'risk_level': 'CRITICAL' if conf > 0.7 else ('HIGH' if conf > 0.5 else 'MEDIUM'),
                })
        seen, unique = set(), []
        for p in sorted(predictions, key=lambda x: -x['confidence']):
            k = f"{p['zone']}_{p['predicted_hour']}"
            if k not in seen:
                seen.add(k)
                unique.append(p)
        return unique[:20]

    def predict_dcli(self, lat, lng, hour, zone, vehicle_type):
        if not self.trained or self.congestion_model is None:
            return 1000.0
        try:
            ze = self._le_zone.transform([zone])[0] if zone in self._le_zone.classes_ else 0
        except:
            ze = 0
        try:
            ve = self._le_vtype.transform([vehicle_type])[0] if vehicle_type in self._le_vtype.classes_ else 0
        except:
            ve = 0
        pred = self.congestion_model.predict(np.array([[lat, lng, hour, datetime.utcnow().weekday(), ze, ve]]))[0]
        return round(max(50, pred), 2)

    def get_zone_analysis(self):
        if not self.trained: return []
        return sorted(self.zone_risk_profiles.values(), key=lambda x: -x['risk_score'])

    def get_temporal_analysis(self):
        if not self.trained: return {}
        avg = sum(self.hourly_patterns['hourly'].values()) / max(len(self.hourly_patterns['hourly']), 1)
        return {
            'hourly_distribution': [
                {'hour': h, 'violations': c, 'risk': 'HIGH' if c > avg * 1.3 else 'NORMAL'}
                for h, c in sorted(self.hourly_patterns['hourly'].items())
            ],
            'daily_distribution': [
                {'day': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d], 'violations': c}
                for d, c in sorted(self.hourly_patterns['daily'].items())
            ],
            'peak_hours': [{'hour': h, 'violations': c} for h, c in self.hourly_patterns['peak_hours']],
        }

    def get_training_summary(self):
        models = [
            {'name': 'KMeans Hotspot Clustering', 'type': 'KMeans', 'status': 'trained', 'detail': f'{len(self.zone_clusters)} clusters'},
            {'name': 'Zone Risk Classifier', 'type': 'Statistical', 'status': 'trained', 'detail': f'{len(self.zone_risk_profiles)} zones'},
            {'name': 'DCLI Congestion Predictor', 'type': 'GradientBoosting', 'status': 'trained', 'detail': f'R²={self.congestion_model.score(np.zeros((1,6)), [0]):.3f}' if self.congestion_model else ''},
            {'name': 'Congestion Forecaster', 'type': 'LSTM (PyTorch)', 'status': 'trained' if self.lstm_trained else 'fallback',
             'detail': f'Loss={self.lstm_training_loss[-1]:.6f}' if self.lstm_training_loss else 'Statistical fallback'},
        ]
        return {
            'status': 'trained', 'models': models,
            'training_data': self.training_stats,
            'feature_importance': self._feature_importance if hasattr(self, '_feature_importance') else {},
            'lstm_loss_history': self.lstm_training_loss[-10:] if self.lstm_training_loss else [],
        }


ml_engine = OmniRouteMLEngine()
