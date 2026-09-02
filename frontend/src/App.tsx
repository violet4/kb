import { Route, Routes } from 'react-router-dom';
import AgentHistoryView from './agents/AgentHistoryView';
import AgentPage from './agents/AgentPage';
import AgentsView from './agents/AgentsView';
import ChannelsView from './channels/ChannelsView';
import DailiesView from './dailies/DailiesView';
import BrowseView from './entities/BrowseView';
import EntityView from './entities/EntityView';
import EventsView from './events/EventsView';
import SearchView from './search/SearchView';
import NavBar from './shared/NavBar';
import UsageView from './usage/UsageView';

export default function App() {
  return (
    // height: 100vh on this outer flex column, not on the content div alone -- NavBar and
    // the content div are siblings, so a height cap on only one of them (tried first) still
    // let the pair together exceed the real viewport height, which is exactly the bug this
    // is fixing, just shifted up one level. With the cap here, flexbox naturally gives NavBar
    // its own content height and the content div the rest via flex: 1 + min-height: 0.
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <NavBar />
      {/* flex: 1 + min-height: 0 (not a hardcoded height) so this div gets exactly the
          viewport height minus NavBar's real height, whatever that happens to be --
          overflowY: auto keeps every other route's natural "scroll if content is taller than
          this space" behavior, just scoped to this div instead of the body. */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          boxSizing: 'border-box',
        }}
      >
        <Routes>
          <Route path="/" element={<DailiesView />} />
          <Route path="/events" element={<EventsView />} />
          <Route path="/usage" element={<UsageView />} />
          <Route path="/agents" element={<AgentsView />} />
          <Route path="/agents/history" element={<AgentHistoryView />} />
          <Route path="/agents/history/:project" element={<AgentHistoryView />} />
          <Route path="/agents/:sessionId" element={<AgentPage />} />
          <Route path="/channels" element={<ChannelsView />} />
          <Route path="/browse/:type" element={<BrowseView />} />
          <Route path="/browse" element={<BrowseView />} />
          <Route path="/search" element={<SearchView />} />
          <Route path="/entities/:type/:id" element={<EntityView />} />
        </Routes>
      </div>
    </div>
  );
}
