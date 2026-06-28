export default function LoginPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-8 py-12">
      <div className="max-w-[400px] w-full mx-auto">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-bamboo-800 tracking-tight mb-1"
            style={{ fontFamily: "var(--font-geist-sans)" }}>
            PM Agent
          </h1>
          <p className="text-sm text-bamboo-500">登录你的账户</p>
        </div>

        {/* 登录表单占位 */}
        <div className="bg-white border border-bamboo-200 rounded-2xl p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-bamboo-700 mb-1.5">
              邮箱
            </label>
            <input
              type="email"
              placeholder="your@email.com"
              className="w-full px-3 py-2 rounded-lg border border-bamboo-200 text-sm text-bamboo-800 placeholder:text-bamboo-400 outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 transition-shadow"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-bamboo-700 mb-1.5">
              密码
            </label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full px-3 py-2 rounded-lg border border-bamboo-200 text-sm text-bamboo-800 placeholder:text-bamboo-400 outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 transition-shadow"
            />
          </div>
          <button className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors cursor-pointer">
            登录
          </button>
        </div>

        <p className="mt-6 text-xs text-bamboo-400 text-center">
          还没有账户？<a href="#" className="text-accent hover:underline">注册</a>
        </p>
      </div>
    </div>
  );
}
