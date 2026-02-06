import './App.css'

function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex flex-col items-center justify-center">
      {/* 배경 장식 */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-20 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse"></div>
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse"></div>
      </div>

      {/* 메인 컨텐츠 */}
      <div className="relative z-10 text-center px-4">
        {/* 아이콘 */}
        <div className="mb-8">
          <span className="text-7xl">🧬</span>
        </div>

        {/* 제목 */}
        <h1 className="text-5xl md:text-6xl font-bold text-white mb-4 tracking-tight">
          Welcome to
          <span className="block bg-gradient-to-r from-cyan-400 to-pink-400 bg-clip-text text-transparent">
            BioJuho DeSci Platform
          </span>
        </h1>

        {/* 부제목 */}
        <p className="text-xl text-gray-300 mb-12 max-w-lg mx-auto">
          탈중앙화 과학의 새로운 시작. 오픈 사이언스와 함께하세요.
        </p>

        {/* 로그인 버튼 */}
        <button className="px-8 py-4 bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-lg rounded-full shadow-lg hover:shadow-cyan-500/25 hover:scale-105 transition-all duration-300 cursor-pointer">
          🚀 Login
        </button>

        {/* 하단 텍스트 */}
        <p className="mt-12 text-gray-400 text-sm">
          Built by Raph & JuPark © 2026
        </p>
      </div>
    </div>
  )
}

export default App
