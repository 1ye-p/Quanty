import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card max-w-sm w-full text-center">
        <div className="text-6xl font-bold text-gray-200 mb-2">404</div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">页面不存在</h1>
        <p className="text-sm text-gray-500 mb-6">
          你访问的页面不存在或已被移除。
        </p>
        <Link to="/" className="btn-primary inline-block">
          返回首页
        </Link>
      </div>
    </div>
  )
}
