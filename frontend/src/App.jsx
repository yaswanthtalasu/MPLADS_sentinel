import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Map, ListChecks, BookOpen, ShieldAlert } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import AlertQueue from './pages/AlertQueue';
import RiskMap from './pages/RiskMap';
import ProjectInvestigation from './pages/ProjectInvestigation';
import Methodology from './pages/Methodology';
import './index.css';

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/alerts', label: 'Alert Queue', icon: ListChecks },
  { to: '/map', label: 'Intelligence Map', icon: Map },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
];

function Sidebar() {
  const { pathname } = useLocation();
  const isActive = (item) => (item.exact ? pathname === item.to : pathname.startsWith(item.to));

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <ShieldAlert size={24} color="#f59e0b" />
        MPLADS Sentinel
      </div>
      <ul className="nav-links">
        {NAV.map((item) => (
          <li key={item.to}>
            <Link to={item.to} className={`nav-item ${isActive(item) ? 'active' : ''}`}>
              <item.icon size={20} />
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <div className="main-content">
          <div className="topbar">
            <div style={{ fontWeight: 600 }}>
              Six-Layer Risk Intelligence for MPLADS Works
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Official ECI 2024 Delimitation 
            </div>
          </div>
          <div className="page-container">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/alerts" element={<AlertQueue />} />
              <Route path="/map" element={<RiskMap />} />
              <Route path="/methodology" element={<Methodology />} />
              {/* Work codes contain slashes, so this route is a splat. */}
              <Route path="/projects/*" element={<ProjectInvestigation />} />
            </Routes>
          </div>
        </div>
      </div>
    </Router>
  );
}
