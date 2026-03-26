interface PaginationProps {
  page: number
  total: number
  pageSize: number
  onPage: (page: number) => void
}

export function Pagination({ page, total, pageSize, onPage }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-end gap-2 mt-4 text-sm">
      <button
        className="px-3 py-1.5 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        이전
      </button>
      <span className="text-slate-500 px-2">
        {page} / {totalPages} (총 {total}건)
      </span>
      <button
        className="px-3 py-1.5 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
      >
        다음
      </button>
    </div>
  )
}
