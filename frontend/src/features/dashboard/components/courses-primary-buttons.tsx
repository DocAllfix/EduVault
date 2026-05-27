/**
 * Primary CTA for the courses section: "Nuovo Corso".
 *
 * Links to the wizard at `/courses/new` (FASE 6.8). TanStack Router
 * type-checks the path against `routeTree.gen.ts` at build time — so
 * if 6.8's route file disappears, this build breaks loudly.
 */

import { Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function CoursesPrimaryButtons() {
  return (
    <Button asChild className='gap-1.5'>
      <Link to='/courses/new'>
        <Plus aria-hidden='true' />
        Nuovo Corso
      </Link>
    </Button>
  )
}
