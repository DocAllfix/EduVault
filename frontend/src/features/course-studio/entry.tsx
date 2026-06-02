/**
 * Course Studio entry page — landing card + auto-opened picker dialog.
 *
 * Reached from the sidebar "Course Studio" item and from the dashboard
 * shortcut. Shows a short explanation and the course picker so the user
 * lands directly on "scegli il corso da modificare".
 */

import { useState } from 'react'
import { Pencil } from 'lucide-react'

import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { CoursePickerDialog } from './components/course-picker-dialog'

export function CourseStudioEntry() {
  // Auto-open the picker once on mount: a key bump triggers the dialog
  // because <CoursePickerDialog> manages its own open state internally.
  // We render an additional invisible trigger that we click programmatically.
  const [autoOpenKey] = useState(0)

  return (
    <>
      <Header>
        <h1 className='text-base font-semibold'>Course Studio</h1>
        <div className='ml-auto flex items-center gap-2'>
          <HelpButton />
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>

      <Main>
        <div className='mx-auto max-w-2xl space-y-6'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>Course Studio</h1>
            <p className='text-muted-foreground mt-2 text-sm'>
              Modifica le slide dei tuoi corsi, sostituisci immagini, riformula
              le note di narrazione e rigenera PPTX/PDF/audio quando hai finito.
            </p>
          </div>

          <Card className='border-brand-primary/30'>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-lg'>
                <Pencil className='size-5' aria-hidden='true' />
                Scegli un corso da modificare
              </CardTitle>
              <CardDescription>
                Apri il selettore per scegliere quale corso aprire in Course
                Studio.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CoursePickerDialog
                trigger={
                  <Button
                    autoFocus
                    size='lg'
                    key={autoOpenKey}
                    className='w-full sm:w-auto'
                  >
                    <Pencil aria-hidden='true' /> Apri il selettore corsi
                  </Button>
                }
              />
            </CardContent>
          </Card>
        </div>
      </Main>
    </>
  )
}
