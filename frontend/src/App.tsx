import { Route, Routes } from 'react-router-dom';
import AgentsView from './agents/AgentsView';
import SessionChatView from './agents/chat/SessionChatView';
import ChannelsView from './channels/ChannelsView';
import DailiesView from './dailies/DailiesView';
import BrowseView from './entities/BrowseView';
import EntityView from './entities/EntityView';
import SearchView from './search/SearchView';
import NavBar from './shared/NavBar';
import UsageView from './usage/UsageView';

export default function App() {
  return (
    <>
      <NavBar />
      <div style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<DailiesView />} />
          <Route path="/usage" element={<UsageView />} />
          <Route path="/agents" element={<AgentsView />} />
          <Route path="/agents/:sessionId" element={<SessionChatView />} />
          <Route path="/channels" element={<ChannelsView />} />
          <Route path="/browse/:type" element={<BrowseView />} />
          <Route path="/browse" element={<BrowseView />} />
          <Route path="/search" element={<SearchView />} />
          <Route path="/entities/:type/:id" element={<EntityView />} />
        </Routes>
      </div>
    </>
  );
}
