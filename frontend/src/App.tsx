import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { PortfolioPage } from "./pages/Portfolio";
import { MarketAnalysis } from "./pages/MarketAnalysis";
import { Trading } from "./pages/Trading";
import { DataManagement } from "./pages/DataManagement";
import { Screening } from "./pages/Screening";
import { RiskManagement } from "./pages/RiskManagement";
import { Backtesting } from "./pages/Backtesting";
import { RegimeDashboard } from "./pages/RegimeDashboard";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/market" element={<MarketAnalysis />} />
        <Route path="/trading" element={<Trading />} />
        <Route path="/data" element={<DataManagement />} />
        <Route path="/screening" element={<Screening />} />
        <Route path="/risk" element={<RiskManagement />} />
        <Route path="/regime" element={<RegimeDashboard />} />
        <Route path="/backtest" element={<Backtesting />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
