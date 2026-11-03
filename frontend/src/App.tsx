import { BrowserRouter, Route, Routes } from 'react-router'
import { AddExpense } from './pages/AddExpense'
import { GroupPage } from './pages/GroupPage'
import { Home } from './pages/Home'
import { InstantSplit } from './pages/InstantSplit'
import { Privacy, Terms } from './pages/Legal'
import { NewGroup } from './pages/NewGroup'
import { NewSplit } from './pages/NewSplit'
import { SplitPage } from './pages/SplitPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/scan" element={<NewSplit />} />
        <Route path="/instant" element={<InstantSplit />} />
        <Route path="/split/:id" element={<SplitPage />} />
        <Route path="/groups/new" element={<NewGroup />} />
        <Route path="/groups/:id" element={<GroupPage />} />
        <Route path="/groups/:id/add" element={<AddExpense />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
      </Routes>
    </BrowserRouter>
  )
}
