import type { EvidenceFile } from "@/shared/api"

export const DOC_TYPES = [
  "наказ",
  "протокол",
  "акт",
  "звіт",
  "лист",
  "довідка",
  "рішення",
  "реєстр",
  "програма",
  "перелік",
  "відомість",
  "журнал",
  "таблиця",
  "знімок",
  "посилання",
]

export const guessDocType = (name: string) => DOC_TYPES.find(t => name.toLowerCase().includes(t)) ?? ""

export const toEvidenceFile = (file: File): EvidenceFile => ({
  file,
  docType: guessDocType(file.name),
  documentDate: null,
})

export const isComplete = (files: EvidenceFile[]) => files.every(f => f.docType.trim() && f.documentDate)

export function appendEvidence(form: FormData, files: EvidenceFile[]) {
  files.forEach(f => {
    form.append("files", f.file)
    form.append("documentTypes", f.docType.trim())
    form.append("documentDates", f.documentDate ?? "")
  })
}
