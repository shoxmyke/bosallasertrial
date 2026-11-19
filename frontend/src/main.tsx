import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProfileBalancing, RGReleasedJobs } from "./pages/Balance";
import CuttingPlan from "./pages/CuttingPlan";
import { BackOrders, Cleaning, RnD } from "./pages/Inputs";
import JobsReleased from "./pages/JobsReleased";
import { JobsCompleted, Output } from "./pages/Reports";
import SchedulePerLaser from "./pages/SchedulePerLaser";
import { DataPage, Profiles } from "./pages/Setup";
import { BCZB, OrderBook, PendingContainers, Plant40, ShutdownStock } from "./pages/Stock";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/average-cutting-plan" replace />} />
          <Route path="/jobs-released" element={<JobsReleased />} />
          <Route path="/back-orders" element={<BackOrders />} />
          <Route path="/profile-balancing" element={<ProfileBalancing />} />
          <Route path="/rg-released-jobs" element={<RGReleasedJobs />} />
          <Route path="/rnd" element={<RnD />} />
          <Route path="/cleaning" element={<Cleaning />} />
          <Route path="/average-cutting-plan" element={<CuttingPlan />} />
          <Route path="/management-report" element={<CuttingPlan management />} />
          <Route path="/schedule-per-laser" element={<SchedulePerLaser />} />
          <Route path="/output" element={<Output />} />
          <Route path="/jobs-completed" element={<JobsCompleted />} />
          <Route path="/plant-40-stock" element={<Plant40 />} />
          <Route path="/bczb-list" element={<BCZB />} />
          <Route path="/pending-containers" element={<PendingContainers />} />
          <Route path="/order-book" element={<OrderBook />} />
          <Route path="/shutdown-stock" element={<ShutdownStock />} />
          <Route path="/profiles-per-product" element={<Profiles />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="*" element={<div className="error-box">Page not found.</div>} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
