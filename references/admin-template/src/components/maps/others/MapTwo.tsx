export default function MapTwo() {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            Map 2
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            Clear view of locations at a glance
          </p>
        </div>
      </div>
      <div className="mt-5">
        <iframe
          src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3650.5145053176284!2d90.42105717591272!3d23.800296778636472!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3755c7e9f37a5a3d%3A0x41d7d1d02e1ed0e4!2sPimjo!5e0!3m2!1sen!2sbd!4v1751871078440!5m2!1sen!2sbd"
          width="303"
          height="300"
          allowFullScreen
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          className="!w-full rounded-xl border border-gray-200 grayscale dark:border-gray-800"
        ></iframe>
      </div>
    </div>
  );
}
