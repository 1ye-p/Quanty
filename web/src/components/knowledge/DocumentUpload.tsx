import { useState, useRef, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { knowledgeApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'

interface DocumentUploadProps {
  onSuccess?: () => void
}

export function DocumentUpload({ onSuccess }: DocumentUploadProps) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [description, setDescription] = useState('')
  const [progress, setProgress] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const qc = useQueryClient()

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('请选择文件')
      setProgress(10)
      return knowledgeApi.upload(file, { tags, description })
    },
    onSuccess: () => {
      toast.success('文档上传成功')
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.all })
      setFile(null)
      setTags([])
      setDescription('')
      setProgress(0)
      onSuccess?.()
    },
    onError: (err: Error) => {
      toast.error(`上传失败：${err.message}`)
      setProgress(0)
    },
  })

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => setDragOver(false), [])

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) setFile(selected)
  }, [])

  const addTag = useCallback(() => {
    const trimmed = tagInput.trim()
    if (trimmed && !tags.includes(trimmed)) {
      setTags(prev => [...prev, trimmed])
    }
    setTagInput('')
  }, [tagInput, tags])

  const removeTag = useCallback((tag: string) => {
    setTags(prev => prev.filter(t => t !== tag))
  }, [])

  const handleTagKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag()
    }
  }, [addTag])

  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-gray-800">上传文档</h3>

      {/* Drag area */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-brand-500 bg-brand-50'
            : file
              ? 'border-green-400 bg-green-50'
              : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.doc,.docx,.md,.py,.ipynb,.txt,.csv,.json,.xlsx"
          className="hidden"
          onChange={handleFileChange}
        />
        {file ? (
          <div>
            <div className="text-lg mb-1">
              {file.name.endsWith('.pdf') ? '📕' :
               file.name.endsWith('.md') ? '📗' :
               file.name.endsWith('.py') ? '🐍' :
               file.name.endsWith('.ipynb') ? '📓' :
               file.name.endsWith('.doc') || file.name.endsWith('.docx') ? '📘' : '📄'}
            </div>
            <div className="text-sm font-medium text-gray-800">{file.name}</div>
            <div className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</div>
          </div>
        ) : (
          <div>
            <div className="text-3xl mb-2 text-gray-400">+</div>
            <div className="text-sm text-gray-500">拖拽文件到此处，或点击选择</div>
            <div className="text-xs text-gray-400 mt-1">支持 PDF、Word、Markdown、Python、Notebook 等</div>
          </div>
        )}
      </div>

      {/* Description */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">描述（可选）</label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="文档描述…"
          rows={2}
          className="input w-full resize-none"
        />
      </div>

      {/* Tags */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">标签</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {tags.map(tag => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-brand-100 text-brand-700"
            >
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="hover:text-brand-900"
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={tagInput}
            onChange={e => setTagInput(e.target.value)}
            onKeyDown={handleTagKeyDown}
            placeholder="输入标签后按 Enter"
            className="input flex-1"
          />
          <button type="button" onClick={addTag} className="btn-primary text-sm px-3">
            添加
          </button>
        </div>
      </div>

      {/* Upload indicator */}
      {uploadMutation.isPending && (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <div className="w-4 h-4 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          上传中...
        </div>
      )}

      {/* Submit */}
      <div className="flex justify-end">
        <button
          className="btn-primary"
          disabled={!file || uploadMutation.isPending}
          onClick={() => uploadMutation.mutate()}
        >
          {uploadMutation.isPending ? '上传中…' : '上传'}
        </button>
      </div>
    </div>
  )
}
