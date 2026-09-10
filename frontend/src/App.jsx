import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import Status from './pages/Status'
import Query from './pages/Query'
import History from './pages/History'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main style={{ minHeight: '100vh' }}>
        <Routes>
          <Route path="/"                  element={<Home />} />
          <Route path="/status/:docId"     element={<Status />} />
          <Route path="/query/:docId"      element={<Query />} />
          <Route path="/history"           element={<History />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}