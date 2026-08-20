import { Route, Routes } from 'react-router-dom';
import DailiesView from './dailies/DailiesView';
import NavBar from './shared/NavBar';
import UsageView from './usage/UsageView';

export default function App() {
  return (
    <>
      <NavBar />
      <Routes>
        <Route
          path="/"
          element={
            <div style={{ maxWidth: 640, margin: '0 auto', padding: 24 }}>
              <DailiesView />
            </div>
          }
        />
        <Route path="/usage" element={<UsageView />} />
      </Routes>
    </>
  );
}
