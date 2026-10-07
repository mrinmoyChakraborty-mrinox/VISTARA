import { ObjectDetail } from "@/components/objects/object-detail";

export default async function ObjectPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  return <ObjectDetail name={decodeURIComponent(name)} />;
}
